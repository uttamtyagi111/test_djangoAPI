from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse

def generate_pdf_from_html(html_string):
    """
    Converts HTML to PDF using xhtml2pdf and returns the PDF file as a byte stream.
    """
    pdf_stream = BytesIO()

    # Convert HTML to PDF
    pisa_status = pisa.CreatePDF(html_string, dest=pdf_stream)

    # Check if there was an error during conversion
    if pisa_status.err:
        return HttpResponse('Error in PDF generation')  # If there was an error, return None
    
    # Rewind the stream to the beginning to read later
    pdf_stream.seek(0)
    # pdf_content = pdf_buffer.getvalue()
    
    return pdf_stream.getvalue()  

def send_email_with_pdf(transaction_id, plan_name, price, expiry_date, user_email):
    """
    Renders the HTML template, converts it to PDF, and sends the PDF as an email attachment.
    """
    print(f"Transaction ID: {transaction_id}, Plan Name: {plan_name}, Price: {price}, Expiry Date: {expiry_date}")
    # Render HTML content from a template
    html_string = render_to_string('subscriptions/invoice_template.html', {
        'transaction_id': transaction_id,
        'plan_name': plan_name,
        'price': price,
        'expiry_date': expiry_date,
    })
    print(html_string)
    # Generate PDF from HTML string
    pdf_content  = generate_pdf_from_html(html_string)

    # Check if the PDF generation was successful
    if not pdf_content :
        return HttpResponse('Error generating PDF', status=500)

    # Create an email message
    email = EmailMessage(
        subject='Your Invoice for Plan Purchase',
        body='Please find your invoice attached.',
        from_email=settings.DEFAULT_FROM_EMAIL,  # Default from email in settings
        to=[user_email],  # The recipient's email
    )

    # Attach the PDF file to the email
    email.attach(f'invoice_{transaction_id}.pdf', pdf_content , 'application/pdf')

    # Send the email
    email.send()

    return HttpResponse('Invoice sent successfully!')
