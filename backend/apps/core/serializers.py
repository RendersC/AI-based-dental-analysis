from rest_framework import serializers
from .models import SystemSettings, OfficialDocument


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = ['key', 'value']
        read_only_fields = ['key']


class OfficialDocumentSerializer(serializers.ModelSerializer):
    """Публичное представление скана для лендинга: только картинка и подпись."""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = OfficialDocument
        fields = ['id', 'caption', 'image_url']

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url
