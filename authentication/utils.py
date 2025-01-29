from django.core.mail import EmailMultiAlternatives,get_connection
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.contrib.auth.models import User
import random
from django.conf import settings
from django.core.mail import EmailMessage

def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(email, otp, username):
    """
    Send an OTP email to the specified address with HTML content.
    """
    connection = get_connection()
    connection.open()
    subject = 'Your Wish Geeks Techserve Registration OTP'
    from_email = settings.DEFAULT_FROM_EMAIL

    html_content = render_to_string('emails/otp_email.html', {'otp': otp, 'username': username})

    email_message = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=from_email,
        to=[email],
    )
    email_message.content_subtype = "html"  
    email_message.send()
    connection.close()


def send_password_reset_email(user, base_url):
    """
    Sends password reset email to the specified user.
    
    :param user: User object (the recipient)
    :param base_url: The base URL of the site to generate the reset link
    :return: None
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_link = f"{base_url}/reset_password/{uidb64}/{token}/"
    

    html_content = render_to_string('emails/password_reset_email.html', {'reset_link': reset_link, 'username': user.username})
    subject = 'Your Wish Geeks Techserve Password Reset Request'
    from_email = settings.DEFAULT_FROM_EMAIL

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=f"Click the link to reset your password: {reset_link}",  
        from_email=from_email,
        to=[user.email]
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send()




def send_welcome_email(user):
    """
    Sends a welcome email to the specified user after successful registration.

    :param user: User object (the recipient)
    :return: None
    """
    # Welcome email content
    html_content = render_to_string(
        'emails/welcome_email.html',  # Template path for the welcome email
        {'username': user.username}  # Context for the template
    )
    subject = 'Welcome to Wish Geeks Techserve!'
    from_email = settings.DEFAULT_FROM_EMAIL

    # Prepare email with both plain text and HTML content
    email_message = EmailMultiAlternatives(
        subject=subject,
        body=html_content,
        from_email=from_email,
        to=[user.email]
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send()
