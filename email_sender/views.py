from rest_framework import serializers
from datetime import timedelta
from django.utils import timezone
from .models import EmailStatusLog  
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from email_validator import validate_email,EmailNotValidError
import dns.resolver
from django.core.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.base import ContentFile
from .models import EmailStatusLog 
from subscriptions.models import UserProfile, Plan
from .serializers import EmailStatusLogSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status,viewsets
from django.core.mail import EmailMessage, get_connection
from django.utils import timezone
from io import StringIO
from django.template import Template, Context
import csv,time,logging,os,boto3,time,uuid
from django.conf import settings
from .serializers import CampaignSerializer,SMTPServerSerializer,UploadedFileSerializer
from .models import   SMTPServer, UploadedFile,Campaign,ContactFile
from django.shortcuts import  get_object_or_404
from .forms import  SMTPServerForm
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.http import JsonResponse


logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def smtp_servers_list(request):
    request_user_id = request.data.get('user_id')
    servers = SMTPServer.objects.filter(user_id=request_user_id)
    serializer = SMTPServerSerializer(servers, many=True)
    return Response({'servers': serializer.data}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def smtp_server_detail(request, pk):
    server = get_object_or_404(SMTPServer, pk=pk, user=request.user)
    serializer = SMTPServerSerializer(server)
    return Response({'server': serializer.data}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def smtp_server_create(request):
    serializer = SMTPServerSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response({'message': 'SMTP server created successfully.', 'server': serializer.data}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def smtp_server_edit(request, pk):
    smtp_server = get_object_or_404(SMTPServer, pk=pk, user=request.user)
    form = SMTPServerForm(request.data, instance=smtp_server)
    
    if form.is_valid():
        smtp_server = form.save(commit=False)
        smtp_server.user = request.user
        smtp_server.save()
        return JsonResponse({'message': 'SMTP server updated successfully.', 'success': True, 'redirect': 'smtp-servers-list'}, status=200)
    else:
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def smtp_server_delete(request, pk):
    smtp_server = SMTPServer.objects.filter(pk=pk, user_id=request.user.id).first()
    if smtp_server is None:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    smtp_server.delete()
    return Response({'meesage':'smtp-server deleted successfully'},status=status.HTTP_204_NO_CONTENT)


def replace_special_characters(content):
    replacements = {
        '\u2019': "'",
        '\u2018': "'",
        '\u201C': '"',
        '\u201D': '"',
    }
    if content:
        for unicode_char, replacement in replacements.items():
            content = content.replace(unicode_char, replacement)
    return content
    



class UploadHTMLToS3(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        logger.debug(f"FILES: {request.FILES}")
        logger.debug(f"DATA: {request.data}")

        html_content = None

        if 'file' in request.FILES:
            file = request.FILES['file']
            if not file.name.endswith('.html'):
                return Response({'error': 'File must be an HTML file.'}, status=status.HTTP_400_BAD_REQUEST)
            html_content = file.read()  
        
        elif 'html_content' in request.data:
            html_content = request.data.get('html_content')
            if not isinstance(html_content, str):
                return Response({'error': 'HTML content must be a string.'}, status=status.HTTP_400_BAD_REQUEST)
            html_content = html_content.encode('utf-8')
        

        if not html_content:
            return Response({'error': 'No HTML content provided.'}, status=status.HTTP_400_BAD_REQUEST)

        file_name = f"{uuid.uuid4()}.html"

        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        try:
            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_name,
                Body=html_content,
                ContentType='text/html'
            )
        except Exception as e:
            logger.error(f"S3 upload failed: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        file_url = f"{settings.AWS_S3_FILE_URL}{file_name}"

        uploaded_file = UploadedFile.objects.create(
            name=file_name,
            file_url=file_url,
            user=request.user  
        )

        return Response({
            'user_id': request.user.id,
            'name': uploaded_file.name,
            'file_url': uploaded_file.file_url,
            'file_key': file_name  
        }, status=status.HTTP_201_CREATED)



class UploadedFileList(APIView):
    permission_classes = [IsAuthenticated]  

    def get(self, request):
        uploaded_files = UploadedFile.objects.filter(user=request.user)  
        serializer = UploadedFileSerializer(uploaded_files, many=True)
        return Response(serializer.data)



class UpdateUploadedFile(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request, file_id):
        uploaded_file = get_object_or_404(UploadedFile, id=file_id)
        
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        existing_file_name = uploaded_file.name
        
        try:
            s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=existing_file_name)
        except Exception as e:
            return Response({'error': f'Failed to delete old file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if 'file' not in request.FILES:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']


        counter = 1
        new_file_name = existing_file_name

        while True:
            try:
                s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=new_file_name)
                new_file_name = f"{existing_file_name.split('.')[0]}({counter}).{existing_file_name.split('.')[-1]}"
                counter += 1
            except s3.exceptions.ClientError:
                break

        try:
            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=new_file_name,
                Body=file,
                ContentType='text/html'  
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        uploaded_file.name = new_file_name
        uploaded_file.file_url = f"{settings.AWS_S3_FILE_URL}{new_file_name}"  
        uploaded_file.save()

        return Response({'file_name': new_file_name, 'file_url': uploaded_file.file_url}, status=status.HTTP_200_OK)

    



class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_serializer = UploadedFileSerializer(data=request.data)
        if file_serializer.is_valid():
            file_serializer.save()
            return Response(file_serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


logger = logging.getLogger(__name__)



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import ContactFile, Contact
import csv
from io import StringIO
from datetime import datetime

class ContactUploadView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user = request.user

        # Check if the user has reached the upload limit
        if ContactFile.objects.filter(user=user).count() >= 10:
            return Response({'error': 'You have reached the maximum limit of 10 contact uploads.'}, status=status.HTTP_400_BAD_REQUEST)

        csv_file = request.FILES.get('csv_file')
        file_name = request.data.get('name')

        if not csv_file:
            return Response({'error': 'CSV file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not file_name:
            return Response({'error': 'File name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check for unique file name
        if ContactFile.objects.filter(user=user, name=file_name).exists():
            return Response({'error': f'A file with the name "{file_name}" already exists. Please use a different name.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate and parse the CSV file
        try:
            decoded_file = csv_file.read().decode('utf-8')
            reader = csv.DictReader(StringIO(decoded_file))

            if not reader.fieldnames:
                raise ValueError("CSV file is missing headers.")
        except Exception as e:
            return Response({'error': f'Invalid CSV file format: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Create a new ContactFile object with the current timestamp
        contact_file = ContactFile.objects.create(user=user, name=file_name)

        contacts = []
        row_count = 0  # Counter for valid rows
        for row in reader:
            if any(row.values()):  # Ensure the row has data
                contacts.append(Contact(contact_file=contact_file, data=row))
                row_count += 1  # Increment only for valid rows
        Contact.objects.bulk_create(contacts)

        return Response({
            'message': 'Contacts uploaded and saved successfully.',
            'file_name': file_name,
            'total_contacts': row_count,  # Number of valid rows excluding the header
            'created_at': contact_file.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')  # Format the creation date
        }, status=status.HTTP_201_CREATED)



class ContactListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        file_id = request.query_params.get('file_id')  # Get file_id from query parameters

        if not file_id:
            return Response({'error': 'file_id is required to fetch contacts.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            contact_file = ContactFile.objects.get(id=file_id, user=user)
        except ContactFile.DoesNotExist:
            return Response({'error': 'Contact file not found or you do not have permission to access it.'}, status=status.HTTP_404_NOT_FOUND)

        # Fetch all contacts for the given file
        contacts = Contact.objects.filter(contact_file=contact_file).values('data')
        return Response({
            'file_name': contact_file.name,
            'contacts': list(contacts)
        }, status=status.HTTP_200_OK)



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Contact, ContactFile
import csv
from io import StringIO

class ContactFileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, file_id):
        """
        Update an existing contact file with a new CSV.
        This allows the user to edit and add new rows with new fields.
        """
        user = request.user

        try:
            # Ensure the file belongs to the user
            contact_file = ContactFile.objects.get(id=file_id, user=user)
        except ContactFile.DoesNotExist:
            return Response({'error': 'Contact file not found or you do not have permission to update it.'}, status=status.HTTP_404_NOT_FOUND)

        # Get the updated contacts from the request
        contacts_data = request.data.get('contacts')
        if not contacts_data:
            return Response({'error': 'No contacts data provided.'}, status=status.HTTP_400_BAD_REQUEST)

        updated_contacts = []  # List to hold updated contacts
        row_count = 0  # Counter for valid rows
        new_rows_count = 0  # Counter for new rows

        for row in contacts_data:
            contact_id = row.get("id")  # Assuming each contact has an 'id'
            if contact_id:  # Update existing contact
                try:
                    contact = Contact.objects.get(id=contact_id, contact_file=contact_file)
                    contact.data.update(row.get("data", {}))  # Update the contact fields
                    contact.save()
                    updated_contacts.append(contact)
                    row_count += 1
                except Contact.DoesNotExist:
                    continue
            else:  # Add new row if id is not found
                new_row = row.get("data", {})
                if new_row:
                    contact = Contact(contact_file=contact_file, data=new_row)
                    contact.save()
                    updated_contacts.append(contact)
                    new_rows_count += 1

        return Response({
            'message': 'Contacts updated and new rows added successfully.',
            'file_name': contact_file.name,
            'total_contacts_updated': row_count,
            'total_new_rows': new_rows_count,  # Number of new rows added
            'created_at': contact_file.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')
        }, status=status.HTTP_200_OK)



class ContactFileDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    def delete(self, request, file_id):
        """
        Delete a contact file and all its associated contacts.
        """
        user = request.user

        try:
            # Ensure the file belongs to the user
            contact_file = ContactFile.objects.get(id=file_id, user=user)
        except ContactFile.DoesNotExist:
            return Response({'error': 'Contact file not found or you do not have permission to delete it.'}, status=status.HTTP_404_NOT_FOUND)

        # Delete the contact file and all its associated contacts
        contact_file.delete()

        return Response({'message': f'Contact file "{contact_file.name}" and its associated contacts have been deleted.'}, status=status.HTTP_200_OK)

 
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Campaign, ContactFile, SMTPServer
from .serializers import CampaignSerializer,ContactSerializer
    
class CampaignView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        serializer = CampaignSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            campaign_name = serializer.validated_data['campaign_name']
            contact_file_id = serializer.validated_data['contact_list']  
            smtp_server_ids = serializer.validated_data['smtp_server_ids']
            delay_seconds = serializer.validated_data.get('delay_seconds', 0)
            subject = serializer.validated_data.get('subject')
            uploaded_file_key = serializer.validated_data['uploaded_file_key']
            display_name = serializer.validated_data['display_name']

            # Validate the contact file
            try:
                contact_file = ContactFile.objects.get(id=contact_file_id)
            except ContactFile.DoesNotExist:
                return Response({'error': 'Contact file not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Save the campaign in the database
            campaign = Campaign.objects.create(
                name=campaign_name,
                user=request.user,
                subject=subject,
                uploaded_file_key=uploaded_file_key,
                display_name=display_name,
                delay_seconds=delay_seconds,
                contact_list=contact_file,  # Assign the ContactFile instance
            )
            smtp_servers = SMTPServer.objects.filter(id__in=smtp_server_ids)
            campaign.smtp_servers.set(smtp_servers)  # Link the SMTP servers to the campaign

            contacts = contact_file.contacts.all()
            contact_serializer = ContactSerializer(contacts, many=True)

            return Response({
                'status': 'Campaign saved successfully.',
                'campaign_id': campaign.id,
                'campaign_name': campaign_name,
                'contacts': contact_serializer.data,  # Include serialized contacts in the response
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
from .models import ContactFile
class SendEmailsView(APIView):
    DEFAULT_EMAIL_LIMIT = 20
    
    def get_html_content_from_s3(self, uploaded_file_key):
        """Fetches HTML content from S3 based on the file key provided."""
        try:
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            s3_object = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=uploaded_file_key)
            return s3_object['Body'].read().decode('utf-8')
        except Exception as e:
            logger.error(f"Error fetching file from S3: {str(e)}")
            raise
        
    def validate_email_domain(self, email):
        """Validate if the email domain has valid MX records."""
        domain = email.split('@')[-1]
        try:
            dns.resolver.resolve(domain, 'MX')
            return True
        except dns.resolver.NoAnswer:
            return False
        except dns.resolver.NXDOMAIN:
            return False
        except Exception as e:
            logger.error(f"DNS lookup failed for domain {domain}: {str(e)}")
            return False

    def post(self, request, *args, **kwargs):
        user = request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        campaign_id = request.data.get('campaign_id')
        user_id = user.id

        try:
            # Fetch campaign and ensure it belongs to the user
            campaign = Campaign.objects.get(id=campaign_id, user_id=user_id)
        except Campaign.DoesNotExist:
            return Response({'error': 'Campaign not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        # Fetch contact list for the campaign
        try:
            contact_file = ContactFile.objects.get(id=campaign.contact_list_id)
            contacts = Contact.objects.filter(contact_file=contact_file)
            contact_list = [contact.data for contact in contacts]
        except ContactFile.DoesNotExist:
            return Response({'error': 'Contact file not found for this campaign.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error accessing contact list: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        if not contact_list:
            return Response({'error': 'No contacts found for this campaign.'}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch SMTP servers
        smtp_server_ids = campaign.smtp_servers.values_list('id', flat=True)
        smtp_servers = SMTPServer.objects.filter(id__in=smtp_server_ids)
        if not smtp_servers.exists():
            return Response({'error': 'No valid SMTP servers found for this campaign.'}, status=status.HTTP_400_BAD_REQUEST)


        # Check user email limits and plan status
        can_send, message = profile.can_send_email()
        if not can_send:
            return Response({"message": message}, status=status.HTTP_400_BAD_REQUEST)

        if profile.plan_status == 'expired':
            return Response({'error': 'Your plan has expired. Please subscribe a plan to continue.'}, status=status.HTTP_403_FORBIDDEN)

        email_limit = profile.current_plan.email_limit if profile.current_plan else self.DEFAULT_EMAIL_LIMIT

        if email_limit != 0 and profile.emails_sent >= email_limit:
            if profile.current_plan is None:
                profile.plan_status = 'expired'
                profile.save()
                return Response(
                    {'error': 'Trial limit exceeded. Please subscribe to a plan to continue.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            return Response(
                {'error': 'Email limit exceeded. Please upgrade your plan to continue.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Retrieve campaign data
        # contact_file = campaign.contact_list
        smtp_server_ids = campaign.smtp_servers.values_list('id', flat=True)
        uploaded_file_key = campaign.uploaded_file_key
        display_name = campaign.display_name
        delay_seconds = campaign.delay_seconds
        subject = campaign.subject

        # Retrieve the email template content
        try:
            file_content = self.get_html_content_from_s3(uploaded_file_key)
        except Exception as e:
            return Response({'error': f'Error fetching file from S3: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # contact_list = []
        # try:
        #     if not campaign.contact_list:
        #         return Response({'error': 'No contact list found for this campaign.'}, status=status.HTTP_400_BAD_REQUEST)
            
        #     with open(campaign.contact_list.path, 'r') as file:
        #         csv_reader = csv.DictReader(file)
        #         contact_list = [row for row in csv_reader]
        # except FileNotFoundError:
        #     logger.error("Contact list file not found.")
        #     return Response({'error': 'Contact list file not found.'}, status=status.HTTP_404_NOT_FOUND)
        # except Exception as e:
        #     logger.error(f"Error processing contact list: {str(e)}")
        #     return Response({'error': 'Error processing the contact list.'}, status=status.HTTP_400_BAD_REQUEST)

        # Parse contact file
        # contact_list = []
        # try:
        #     contact_file_content = open(contact_file.file.path, 'r').read()
        #     csv_reader = csv.DictReader(StringIO(contact_file_content))
        #     contact_list = [row for row in csv_reader]
        # except Exception as e:
        #     logger.error(f"Error processing contact list: {str(e)}")
        #     return Response({'error': 'Error processing the contact list.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # contact_list = []
        # try:
        #     with open(contact_file_path, 'r') as file:
        #         csv_reader = csv.DictReader(file)
        #         contact_list = [row for row in csv_reader]
        # except FileNotFoundError:
        #     return Response({'error': 'Contact list file not found.'}, status=status.HTTP_404_NOT_FOUND)
        # except Exception as e:
        #     return Response({'error': f'Error processing contact list: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        
        total_contacts = len(contact_list)
        successful_sends = 0
        failed_sends = 0
        email_statuses = []
        channel_layer = get_channel_layer()
        smtp_servers = SMTPServer.objects.filter(id__in=smtp_server_ids)
        num_smtp_servers = len(smtp_servers)

        for i, recipient in enumerate(contact_list):
            if email_limit != 0 and profile.emails_sent >= email_limit:
                for remaining_recipient in contact_list[i:]:
                    failed_sends += 1
                    status_message = 'Failed to send: Email limit exceeded'
                    timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                    email_statuses.append({
                        'email': remaining_recipient.get('Email'),
                        'status': status_message,
                        'timestamp': timestamp,
                    })
                    async_to_sync(channel_layer.group_send)(
                    f'email_status_{user_id}',
                    {
                        'type': 'send_status_update',
                        'email': remaining_recipient.get('Email'),
                        'status': status_message,
                        'timestamp': timestamp,
                    })
                break
            
            recipient_email = recipient.get('Email')
            
            try:
                validated_email = validate_email(recipient_email).email
            except EmailNotValidError as e:
                failed_sends += 1
                status_message = f'Failed to send: {str(e)}'
                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                email_statuses.append({
                    'email': recipient_email,
                    'status': status_message,
                    'timestamp': timestamp,
                })
                
                async_to_sync(channel_layer.group_send)(
                    f'email_status_{user_id}',
                    {
                        'type': 'send_status_update',
                        'email': recipient_email,
                        'status': status_message,
                        'timestamp': timestamp,
                    }
                )
                continue
            
            if not self.validate_email_domain(validated_email):
                failed_sends += 1
                status_message = 'Failed to send: Invalid domain'
                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                email_statuses.append({
                    'email': validated_email,
                    'status': status_message,
                    'timestamp': timestamp,
                })
                async_to_sync(channel_layer.group_send)(
                    f'email_status_{user_id}',
                    {
                        'type': 'send_status_update',
                        'email': validated_email,
                        'status': status_message,
                        'timestamp': timestamp,
                    }
                )
                continue
            
            context = {
                'firstName': recipient.get('firstName'),
                'lastName': recipient.get('lastName'),
                'companyName': recipient.get('companyName'),
                'display_name': display_name,
            }
            try:
                template = Template(file_content)
                context_data = Context(context)
                email_content = template.render(context_data)
            except Exception as e:
                failed_sends += 1
                status_message = f'Failed to send: Error formatting email content - {str(e)}'
                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                email_statuses.append({
                    'email': validated_email,
                    'status': status_message,
                    'timestamp': timestamp,
                })
                async_to_sync(channel_layer.group_send)(
                    f'email_status_{user_id}',
                    {
                        'type': 'send_status_update',
                        'email': validated_email,
                        'status': status_message,
                        'timestamp': timestamp,
                    }
                )
                continue


            smtp_server = smtp_servers[i % num_smtp_servers]
            email = EmailMessage(
                subject=subject,
                body=email_content,
                from_email=f'{display_name} <{smtp_server.username}>',
                to=[recipient_email]
            )
            email.content_subtype = 'html'
            
            try:
                connection = get_connection(
                    backend='django.core.mail.backends.smtp.EmailBackend',
                    host=smtp_server.host,
                    port=smtp_server.port,
                    username=smtp_server.username,
                    password=smtp_server.password,
                    use_tls=smtp_server.use_tls,
                )
                email.connection = connection
                email.send()
                status_message = 'Sent successfully'
                successful_sends += 1
                profile.increment_email_count()
                profile.save()
            except Exception as e:
                status_message = f'Failed to send: {str(e)}'
                failed_sends += 1
                logger.error(f"Error sending email to {recipient_email}: {str(e)}")

            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            email_statuses.append({
                'email': validated_email,
                'status': status_message,
                'timestamp': timestamp,
                'from_email': smtp_server.username,
                'smtp_server': smtp_server.host,
            })
            EmailStatusLog.objects.create(
                user=user,
                email=validated_email,
                status=status_message,
                from_email=smtp_server.username,
                smtp_server=smtp_server.host,
            )
            
            async_to_sync(channel_layer.group_send)(
                f'email_status_{user_id}',
                {
                    'type': 'send_status_update',
                    'email': validated_email,
                    'status': status_message,
                    'timestamp': timestamp,
                }
            )

            if delay_seconds > 0:
                time.sleep(delay_seconds) 

        return Response({
            'status': 'All emails processed',
            'total_emails': total_contacts,
            'successful_sends': successful_sends,
            'failed_sends': failed_sends,
            'email_statuses': email_statuses
        }, status=status.HTTP_200_OK)






    
class EmailStatusAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        user = request.user  

        total_emails = EmailStatusLog.objects.filter(user=user).count()
        successful_sends = EmailStatusLog.objects.filter(user=user, status='Sent successfully').count()
        failed_sends = EmailStatusLog.objects.filter(user=user, status__startswith='Failed').count()

        analytics_data = {
            'total_emails': total_emails,
            'successful_sends': successful_sends,
            'failed_sends': failed_sends,
        }

        return Response(analytics_data, status=status.HTTP_200_OK)    
    
    
    
    

class EmailStatusByDateRangeView(APIView):
    permission_classes = [IsAuthenticated]
    
    class DateRangeSerializer(serializers.Serializer):
        start_date = serializers.DateField(required=True)
        end_date = serializers.DateField(required=True)

        def validate(self, data):
            start_date = data.get('start_date')
            end_date = data.get('end_date')

            delta = end_date - start_date
            if delta.days > 7:
                raise ValidationError("The date range cannot be more than 7 days.")
            return data

    def get(self, request, *args, **kwargs):
        user = request.user

        serializer = self.DateRangeSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        start_date = serializer.validated_data['start_date']
        end_date = serializer.validated_data['end_date']


        today = timezone.now().date()
        if end_date > today:
            raise ValidationError("End date cannot be in the future.")

        if start_date > end_date:
            raise ValidationError("Start date cannot be after end date.")

        successful_sends = []
        failed_sends = []
        labels = []

        for i in range((end_date - start_date).days + 1):
            day = start_date + timedelta(days=i)
            labels.append(day.strftime('%Y-%m-%d'))

            successful_sends.append(
                EmailStatusLog.objects.filter(
                    user=user,
                    status='Sent successfully',
                    timestamp__date=day
                ).count()
            )

            failed_sends.append(
                EmailStatusLog.objects.filter(
                    user=user,
                    status__startswith='Failed',
                    timestamp__date=day
                ).count()
            )

        analytics_data = {
            'labels': labels,
            'successful_sends': successful_sends,
            'failed_sends': failed_sends,
        }

        return Response(analytics_data, status=status.HTTP_200_OK)



    
    
    
    

