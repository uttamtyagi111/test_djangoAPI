from rest_framework import serializers
from .models import  SMTPServer,UploadedFile,EmailStatusLog,ContactFile,Campaign
        
class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = ['id', 'user_id', 'name', 'file_url']  


class EmailStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailStatusLog
        fields = ['id','user', 'email', 'status', 'timestamp', 'from_email', 'smtp_server']



class SMTPServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SMTPServer
        fields = ['id', 'name', 'host', 'port', 'username', 'password', 'use_tls']


        

# from rest_framework import serializers

# class CampaignSerializer(serializers.Serializer):
#     campaign_name = serializers.CharField(max_length=255)  # Name of the campaign
#     smtp_server_ids = serializers.ListField(
#         child=serializers.IntegerField(),  # List of SMTP server IDs
#         write_only=True
#     )
#     display_name = serializers.CharField()  # Display name for the email sender
#     subject = serializers.CharField(max_length=255)  # Email subject
#     delay_seconds = serializers.IntegerField(required=False, default=0)  # Delay between sending emails
#     # email_list = serializers.IntegerField()  # The CSV file for the contact list
#     uploaded_file_key = serializers.CharField()  # Key for accessing the file in S3 storage
#     contact_list = serializers.IntegerField()
    
#     # Validation for email list file
#     def validate_email_list(self, value):
#         if not ContactFile.objects.filter(id=value).exists():
#             raise serializers.ValidationError("The provided contact file ID does not exist.")
#         return value

#     # Validate if SMTP server IDs are provided
#     def validate(self, data):
#         if not data.get('smtp_server_ids'):
#             raise serializers.ValidationError("At least one SMTP server ID is required.")
#         return data
from rest_framework import serializers
from .models import ContactFile, SMTPServer

class CampaignSerializer(serializers.Serializer):
    campaign_name = serializers.CharField(max_length=255, help_text="Name of the campaign")
    smtp_server_ids = serializers.ListField(
        child=serializers.IntegerField(),  # List of SMTP server IDs
        write_only=True,
        help_text="List of SMTP server IDs"
    )
    display_name = serializers.CharField(max_length=255, help_text="Display name for the email sender")
    subject = serializers.CharField(max_length=255, help_text="Email subject")
    delay_seconds = serializers.IntegerField(required=False, default=0, help_text="Delay between sending emails")
    uploaded_file_key = serializers.CharField(max_length=255, help_text="Key for accessing the file in storage")
    contact_list = serializers.IntegerField(help_text="ID of the contact file associated with the campaign")

    # Validate `contact_list` to ensure the ContactFile exists
    def validate_contact_list(self, value):
        if not ContactFile.objects.filter(id=value).exists():
            raise serializers.ValidationError("The provided contact file ID does not exist.")
        return value

    # Validate `smtp_server_ids` to ensure they refer to existing SMTPServer instances
    def validate_smtp_server_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one SMTP server ID is required.")
        non_existing_ids = [id for id in value if not SMTPServer.objects.filter(id=id).exists()]
        if non_existing_ids:
            raise serializers.ValidationError(f"The following SMTP server IDs do not exist: {non_existing_ids}")
        return value

    # General validation to check additional conditions if necessary
    def validate(self, data):
        # Example: Ensure `delay_seconds` is not negative
        if data.get('delay_seconds', 0) < 0:
            raise serializers.ValidationError("Delay seconds cannot be negative.")
        return data
    
    # Validation for unique campaign name
    def validate_campaign_name(self, value):
        """Ensure the campaign name is unique for the user."""
        request_user = self.context.get('request').user
        if Campaign.objects.filter(name=value, user=request_user).exists():
            raise serializers.ValidationError("A campaign with this name already exists for the user.")
        return value

    


from rest_framework import serializers
from .models import Contact

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'contact_file', 'data']
