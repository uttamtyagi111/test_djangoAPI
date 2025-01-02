from rest_framework import serializers
from .models import  SMTPServer,UploadedFile,EmailStatusLog
        
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


        

class EmailSendSerializer(serializers.Serializer):
    smtp_server_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )
    display_name = serializers.CharField()
    subject = serializers.CharField(max_length=255) 
    delay_seconds = serializers.IntegerField(required=False, default=0) 
    email_list = serializers.FileField()
    uploaded_file_key = serializers.CharField() 
    
    def validate_email_list(self, value):
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("Only CSV files are accepted.")
        return value


    def validate(self, data):
        if not data.get('smtp_server_ids'):
            raise serializers.ValidationError("At least one SMTP server ID is required.")
        return data