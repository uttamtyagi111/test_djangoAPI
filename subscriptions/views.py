from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import razorpay
import logging
from .models import Plan, UserProfile
from razorpay.errors import BadRequestError, ServerError



logger = logging.getLogger(__name__)
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET_KEY))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        plan_status = user_profile.check_plan_status()
        
        data = {
            'username': request.user.username,
            'email_count': user_profile.emails_sent,
            'plan_name': user_profile.plan_name,
            'plan_status': user_profile.plan_status,
            'plan_expiry_date': user_profile.plan_expiration_date
            
        }
        return Response(data, status=status.HTTP_200_OK)
    except UserProfile.DoesNotExist:
        return Response({'message': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def get_available_plans(request):
    plans = Plan.objects.all()
    data = [{'id': plan.id, 'name': plan.name, 'email_limit': plan.email_limit, 'duration_days': plan.duration_days} for plan in plans]
    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def choose_plan_view(request):
    """
    Allows authenticated users to choose a plan.
    """
    plan_name = request.data.get('plan_name')
    
    if plan_name not in ['basic', 'premium']:
        return Response({'message': 'Invalid plan selected. Choose either "basic" or "premium".'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:

        user_profile = UserProfile.objects.get(user=request.user)
        plan = Plan.objects.get(name__iexact=plan_name)
        
        user_profile.plan_name = plan.name
        user_profile.current_plan = plan
        user_profile.plan_status = "active"
        user_profile.emails_sent = 0  
        user_profile.plan_expiration_date = timezone.now() + timedelta(days=plan.duration_days)
        user_profile.save()

        return Response({'message': f'Plan successfully updated to {plan_name}.'}, status=status.HTTP_200_OK)
    except UserProfile.DoesNotExist:
        return Response({'message': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Plan.DoesNotExist:
        return Response({'message': 'Selected plan not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def upgrade_plan(request):
    """
    Allows authenticated users to upgrade to a new plan.
    """
    plan_name = request.data.get('plan_name')
    
    if plan_name not in ['basic', 'premium']:
        return Response({'message': 'Invalid plan selected. Choose either "basic" or "premium".'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_profile = UserProfile.objects.get(user=request.user)
        new_plan = Plan.objects.get(name__iexact=plan_name)
        
        user_profile.plan_name = new_plan.name
        user_profile.current_plan = new_plan
        user_profile.plan_status = "active"
        user_profile.emails_sent = 0  
        user_profile.plan_expiration_date = timezone.now() + timedelta(days=new_plan.duration_days)
        user_profile.save()
        
        return Response({'message': f'Plan successfully upgraded to {plan_name}.'}, status=status.HTTP_200_OK)
    except UserProfile.DoesNotExist:
        return Response({'message': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Plan.DoesNotExist:
        return Response({'message': 'Selected plan not found.'}, status=status.HTTP_404_NOT_FOUND)


logger = logging.getLogger(__name__)    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """
    Creates an order for the selected plan and updates the user profile with the plan details upon order creation.
    """
    plan_name = request.data.get('plan_name')
    if plan_name not in ['basic', 'premium']:
        return Response({'message': 'Invalid plan selected. Choose either "basic" or "premium".'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        plan = Plan.objects.get(name__iexact=plan_name)
        order_amount = int(plan.price * 100)
        order_currency = 'INR'
        order_receipt = f'order_rcptid_{request.user.id}'

        razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET_KEY))
        razorpay_order = razorpay_client.order.create({
            'amount': order_amount,
            'currency': order_currency,
            'receipt': order_receipt,
            'payment_capture': '1'
        })

    except Plan.DoesNotExist:
        return Response({'message': 'Selected plan not found.'}, status=status.HTTP_404_NOT_FOUND)
    except BadRequestError as e:
        logger.error(f'Bad Request: {e}')
        return Response({'message': 'Error creating Razorpay order due to bad request.'}, status=status.HTTP_400_BAD_REQUEST)
    except ServerError as e:
        logger.error(f'Server Error: {e}')
        return Response({'message': 'Error creating Razorpay order due to server issue.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Unexpected Error: {e}')
        return Response({'message': 'Error creating Razorpay order.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_profile = request.user.userprofile
        user_profile.current_plan = plan
        user_profile.razorpay_order_id = razorpay_order['id']
        user_profile.save()
    except UserProfile.DoesNotExist:
        return Response({'message': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'amount': order_amount,
        'currency': order_currency,
        'plan_name': plan.name,
        'message': f'Order created successfully for the {plan_name} plan with updated profile details.'
    }, status=status.HTTP_200_OK)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handle_payment_callback(request):
    payload = request.data
    razorpay_order_id = payload.get('razorpay_order_id')
    razorpay_payment_id = payload.get('razorpay_payment_id')
    razorpay_signature = payload.get('razorpay_signature')

    razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET_KEY))

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })
        try:
            user_profile = UserProfile.objects.get(razorpay_order_id=razorpay_order_id)
        except UserProfile.DoesNotExist:
            return Response({'message': 'Order not found for this user profile.'}, status=404)

        plan = user_profile.current_plan
        user_profile.plan_name = plan.name
        user_profile.plan_expiration_date = timezone.now() + timedelta(days=plan.duration_days)
        user_profile.plan_status = 'active'
        user_profile.razorpay_payment_id = razorpay_payment_id
        user_profile.save()

        return Response({'message': 'Payment successful, plan activated!'}, status=200)

    except razorpay.errors.SignatureVerificationError:
        return Response({'message': 'Invalid payment signature.'}, status=400)

    except Exception as e:
        return Response({'message': 'An error occurred during payment processing.'}, status=500)

