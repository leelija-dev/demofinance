from rest_framework import serializers
from agent.models import Agent
import os
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.templatetags.static import static
from django.db.models import Sum
from loan.models import EmiCollectionDetail
from savings.models import SavingsCollection

class AgentSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()
    id_proof = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)
    branch = serializers.PrimaryKeyRelatedField(queryset=Agent._meta.get_field('branch').related_model.objects.all(), required=False)
    unverified_collected_amount = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = ['agent_id', 'full_name', 'email', 'phone', 'area', 'status', 'is_demo', 'password', 'branch', 'unverified_collected_amount', 'photo', 'id_proof']
        read_only_fields = ['agent_id']

    def get_photo(self, obj):
        try:
            photo = getattr(obj, 'photo', None)
            if photo and hasattr(photo, 'name') and photo.name:
                # Return the file name instead of URL to avoid Cloudinary issues
                return str(photo.name)
        except Exception:
            pass
        return None

    def get_id_proof(self, obj):
        try:
            id_proof = getattr(obj, 'id_proof', None)
            if id_proof and hasattr(id_proof, 'name') and id_proof.name:
                # Return the file name instead of URL to avoid Cloudinary issues
                return str(id_proof.name)
        except Exception:
            pass
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data

    def get_unverified_collected_amount(self, obj):
        emi_total = (
            EmiCollectionDetail.objects.filter(
                collected_by_agent=obj,
                collected=True,
                status__in=['collected'],
            ).aggregate(total=(Sum('amount_received') + Sum('penalty_received')))['total']
            or 0
        )

        savings_total = (
            SavingsCollection.objects.filter(
                collected_by_agent=obj,
                is_collected=True,
                is_deposited_to_branch=False,
                collection_type__in=['rd_installment', 'fd_deposit'],
            ).aggregate(total=Sum('amount'))['total']
            or 0
        )

        return (emi_total or 0) + (savings_total or 0)

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        if password:
            validated_data['password_hash'] = make_password(password)
        agent = Agent(**validated_data)
        agent.save()
        return agent

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            validated_data['password_hash'] = make_password(password)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance