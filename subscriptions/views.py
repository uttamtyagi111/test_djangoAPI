import base64
import hashlib
import json
import requests
from django.http import JsonResponse, HttpResponseBadRequest
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
            'plan_start_date' : user_profile.plan_start_date,
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
    
    if plan_name not in ['basic','standard', 'premium','elite']:
        return Response({'message': 'Invalid plan selected. Choose either "basic" or "premium".'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:

        user_profile = UserProfile.objects.get(user=request.user)
        plan = Plan.objects.get(name__iexact=plan_name)
        
        user_profile.plan_name = plan.name
        user_profile.current_plan = plan
        user_profile.plan_status = "active"
        user_profile.emails_sent = 0
        user_profile.plan_start_date = timezone.now()  
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
    
    if plan_name not in ['basic', 'standard','premium','elite']:
        return Response({'message': 'Invalid plan selected. Choose either "basic" or "premium".'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_profile = UserProfile.objects.get(user=request.user)
        new_plan = Plan.objects.get(name__iexact=plan_name)
        
        user_profile.plan_name = new_plan.name
        user_profile.current_plan = new_plan
        user_profile.plan_status = "active"
        user_profile.emails_sent = 0  
        user_profile.plan_start_date = timezone.now()  
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
    if plan_name not in ['basic', 'standard','premium','elite']:
        return Response({'message': 'Invalid plan selected. Choose either "basic" or "standard" or "premium" or "elite".'}, status=status.HTTP_400_BAD_REQUEST)

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
        user_profile = UserProfile.objects.get(user=request.user)
        user_profile = request.user.userprofile
        user_profile.current_plan = plan
        user_profile.razorpay_order_id = razorpay_order['id']
        user_profile.payment_status = "initiated"
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
        user_profile.plan_start_date = timezone.now()
        user_profile.plan_expiration_date = timezone.now() + timedelta(days=plan.duration_days)
        user_profile.plan_status = 'active'
        user_profile.payment_status = 'paid'
        user_profile.razorpay_payment_id = razorpay_payment_id
        user_profile.save()

        return Response({'message': 'Payment successful, plan activated!'}, status=200)

    except razorpay.errors.SignatureVerificationError:
        return Response({'message': 'Invalid payment signature.'}, status=400)

    except Exception as e:
        return Response({'message': 'An error occurred during payment processing.'}, status=500)



VERIFY_URL = settings.VERIFY_URL
MERCHANT_ID = settings.MERCHANT_ID
SALT_KEY = settings.SALT_KEY
PHONEPE_URL = settings.PHONEPE_URL

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    try:
        # Parse the incoming data
        req_data = json.loads(request.body)
        merchant_transaction_id = req_data.get("transactionId")
        name = req_data.get("name")
        amount = int(req_data.get("amount", 0)) * 100  # Convert to paise
        mobile = req_data.get("mobile")
        plan_name = req_data.get("plan_name")
        
        if plan_name not in ['basic', 'standard','premium','elite']:
            return Response({'message': 'Invalid plan selected. Choose either "basic" or "standard" or "premium" or "elite".'}, status=status.HTTP_400_BAD_REQUEST)

        # Check for missing required fields
        missing_fields = []
        if not merchant_transaction_id:
            missing_fields.append("transactionId")
        if not name:
            missing_fields.append("name")
        if not amount:
            missing_fields.append("amount")
        if not mobile:
            missing_fields.append("mobile")
        if not plan_name:
            missing_fields.append("plan_name")

        if missing_fields:
            return JsonResponse({"error": "Missing required fields", "missing_fields": missing_fields}, status=400)


        # Fetch the selected plan
        try:
            plan = Plan.objects.get(name__iexact=plan_name)
        except Plan.DoesNotExist:
            return JsonResponse({"error": "Plan not found"}, status=404)

        # Create the PhonePe payload
        payload = {
            "merchantId": MERCHANT_ID,
            "merchantTransactionId": merchant_transaction_id,
            "message": "Payment Initiated",
            "name": name,
            "amount": amount,
            "redirectUrl": f"http://localhost:8000/verify-payment/?id={merchant_transaction_id}",
            "redirectMode": "POST",
            "callbackUrl": f"http://localhost:8000/payment-success?id={merchant_transaction_id}",
            "mobileNumber": mobile,
            "paymentInstrument": {"type": "PAY_PAGE"},
        }

        # Encode payload and generate checksum
        payload_encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        checksum_string = f"{payload_encoded}/pg/v1/pay{SALT_KEY}"
        checksum_hash = hashlib.sha256(checksum_string.encode()).hexdigest()
        checksum = f"{checksum_hash}###1"

        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
        }
        api_payload = {"request": payload_encoded}

        # Call PhonePe API
        response = requests.post(PHONEPE_URL, headers=headers, json=api_payload)
        response_data = response.json()

        if response_data.get("success"):
            # Save transaction details to user profile
            user_profile = request.user.userprofile
            user_profile.phonepe_transaction_id = merchant_transaction_id
            user_profile.current_plan = plan
            user_profile.plan_status = "inactive" # Set as inactive until payment is confirmed
            user_profile.payment_status = "initiated"
            user_profile.pending_plan_id = plan.id
            user_profile.save()

            redirect_url = response_data["data"]["instrumentResponse"]["redirectInfo"]["url"]
            return JsonResponse({"redirect_url": redirect_url}, status=200)
        else:
            return JsonResponse(response_data, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)



import hashlib
import requests
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect

from rest_framework.permissions import AllowAny

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_payment(request):
    try:
        merchant_transaction_id = request.GET.get("id")
        if not merchant_transaction_id:
            return JsonResponse({"error": "Transaction ID is required"}, status=400)

        # Generate checksum for verifying the payment
        checksum_string = f"/pg/v1/status/{MERCHANT_ID}/{merchant_transaction_id}{SALT_KEY}"
        checksum_hash = hashlib.sha256(checksum_string.encode()).hexdigest()
        checksum = f"{checksum_hash}###1"

        # Prepare headers for the API call
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "X-MERCHANT-ID": MERCHANT_ID,
        }

        # Call PhonePe API to verify payment status
        response = requests.get(f"{VERIFY_URL}/{MERCHANT_ID}/{merchant_transaction_id}", headers=headers)
        response_data = response.json()

        if response_data.get("success"):
            # Extract payment status
            payment_status = response_data.get("data", {}).get("status", "").lower()

            # Find the user profile associated with the transaction
            user_profile = UserProfile.objects.get(phonepe_transaction_id=merchant_transaction_id)

            if payment_status == "":
                # Retrieve the plan details from the database
                plan = Plan.objects.get(id=user_profile.pending_plan_id)  # Assuming `pending_plan_id` was saved earlier

                # Activate the plan using the activate_plan method
                user_profile.activate_plan(plan)

                # Redirect or respond with success
                return redirect("http://localhost:8000/payment-success")
            else:
                # Handle failed or pending payments
                user_profile.plan_status = "inactive"
                user_profile.payment_status = payment_status    
                user_profile.save()

                return redirect("http://localhost:8000/payment-failed")
        else:
            # API call failed, log the error and return failure
            return JsonResponse({"error": response_data.get("message", "Payment verification failed.")}, status=400)

    except Plan.DoesNotExist:
        return JsonResponse({"error": "Selected plan does not exist."}, status=404)
    except UserProfile.DoesNotExist:
        return JsonResponse({"error": "Transaction ID not associated with any user profile."}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


from django.shortcuts import render

def payment_success(request):
    """Handle successful payments."""
    return render(request, 'subscriptions\success.html')

def payment_failed(request):
    """Handle failed payments."""
    return render(request, 'subscriptions/failed.html')

