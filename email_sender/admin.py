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

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('contact_file', 'data')  # Fields to display in the list view
    list_filter = ('contact_file',)  # Filter by contact file
    search_fields = ('data',)  # Enable search for the data field
    readonly_fields = ('data',)  # Make the data field read-only

from django.contrib import admin
from .models import Campaign

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'subject', 'uploaded_file_key', 'display_name', 'delay_seconds', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('name', 'subject', 'user__email')
    ordering = ('-created_at',)
