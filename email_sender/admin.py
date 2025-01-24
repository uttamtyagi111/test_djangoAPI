from django.contrib import admin
from .models import  SMTPServer,UploadedFile,EmailStatusLog

@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'name', 'file_url')

@admin.register(SMTPServer)
class SMTPServerAdmin(admin.ModelAdmin):
    list_display = ('id','user_id','name', 'host', 'port', 'username', 'use_tls')
    search_fields = ('name', 'host', 'username')
    ordering = ('name',)


@admin.register(EmailStatusLog)
class EmailStatusLogAdmin(admin.ModelAdmin):
    list_display = ('id','email', 'status', 'timestamp', 'user', 'from_email', 'smtp_server')  
    search_fields = ('email', 'status', 'from_email')

    def user(self, obj):
        return obj.user.username  

    user.short_description = 'User' 
    
    
from django.contrib import admin
from .models import ContactFile, Contact

class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0  # No extra empty rows by default
    fields = ('data',)
    readonly_fields = ('data',)  # Make the data field read-only for admin display

@admin.register(ContactFile)
class ContactFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'uploaded_at')  # Fields to display in the list view
    list_filter = ('user', 'uploaded_at')  # Filters for easier navigation
    search_fields = ('name', 'user__username')  # Search functionality
    inlines = [ContactInline]  # Display associated contacts inline

from django.contrib import admin
from django import forms
from .models import Contact

class ContactAdminForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = '__all__'
    
    # If `data` is a JSONField, you can create a custom widget for better editing
    data = forms.JSONField(widget=forms.Textarea(attrs={'rows': 4, 'cols': 50}))

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    form = ContactAdminForm
    list_display = ('contact_file', 'data')  # Display contact file and email in the list
    list_filter = ('contact_file',)  # Filter by contact file
    search_fields = ('contact_file__name',)  # Search by contact file name and email inside data
    readonly_fields = ()  # Make the data field editable
    actions = ['make_unsubscribed']

    # Optionally, create a custom function to extract and display email from data
    def email(self, obj):
        return obj.data.get('email', 'N/A')
    email.short_description = 'Email'

    # Optional action for unsubscribing contacts
    def make_unsubscribed(self, request, queryset):
        # Logic for unsubscribing the contacts (You can implement this based on your requirements)
        pass
    make_unsubscribed.short_description = 'Mark selected contacts as unsubscribed'
 # Make the data field read-only

from django.contrib import admin
from .models import Campaign

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'subject', 'uploaded_file_key', 'display_name', 'delay_seconds', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('name', 'subject', 'user__email')
    ordering = ('-created_at',)


from django.contrib import admin
from .models import Unsubscribed

class UnsubscribedAdmin(admin.ModelAdmin):
    list_display = ('contact', 'contact_file', 'unsubscribed_at')
    list_filter = ('unsubscribed_at', 'contact_file')  # You can filter by the contact file and unsubscription date
    search_fields = ('contact__data__email', 'contact_file__name')  # Search by email and contact file name
    ordering = ('-unsubscribed_at',)  # Order by the latest unsubscribed time

admin.site.register(Unsubscribed, UnsubscribedAdmin)
