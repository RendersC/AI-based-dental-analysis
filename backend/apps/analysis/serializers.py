from rest_framework import serializers
from .models import Analysis, AnalysisPhoto, AGE_GROUP_CHOICES

UNDERAGE_GROUPS = {'milk', 'mixed', 'permanent_teen'}
MAX_PHOTOS = 5
# Экспресс-оценка — режим «одно фото за пару минут». Больше одного снимка
# смысла не имеет: без индикатора мы всё равно даём только общее впечатление.
MAX_EXPRESS_PHOTOS = 1
# Заметка пользователя — личная пометка, а не поле для длинного текста.
MAX_NOTE_LENGTH = 1000


class AnalysisPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisPhoto
        fields = ['id', 'photo', 'overlay', 'order']
        read_only_fields = fields


class AnalysisSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    photos = AnalysisPhotoSerializer(many=True, read_only=True)
    age_group_display = serializers.CharField(source='get_age_group_display', read_only=True)
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = Analysis
        fields = [
            'id', 'user_id', 'kind', 'kind_display',
            'photo_url', 'photos', 'age_group', 'age_group_display',
            'legal_rep_consent', 'score',
            'fresh_plaque_percent', 'old_plaque_percent', 'cv_measured',
            'problem_zones', 'observations', 'recommendations', 'dynamics_text',
            'note', 'doctor_comment', 'ai_model', 'is_valid',
            'attempt_deducted', 'created_at',
        ]
        read_only_fields = fields


class AnalysisCreateSerializer(serializers.Serializer):
    """Валидирует только метаданные. Фото обрабатываются вручную в view из request.FILES."""
    age_group = serializers.ChoiceField(choices=[c[0] for c in AGE_GROUP_CHOICES])
    legal_rep_consent = serializers.BooleanField(required=False, default=False)
    note = serializers.CharField(required=False, allow_blank=True, default='', max_length=MAX_NOTE_LENGTH)

    def validate(self, data):
        ag = data['age_group']
        if ag in UNDERAGE_GROUPS and not data.get('legal_rep_consent'):
            raise serializers.ValidationError({
                'legal_rep_consent': 'Для пациента до 18 лет требуется согласие законного представителя'
            })
        return data
