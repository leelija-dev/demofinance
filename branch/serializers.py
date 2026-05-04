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
    photo = serializers.ImageField(max_length=None, use_url=True, required=False)
    id_proof = serializers.ImageField(max_length=None, use_url=True, required=False)
    password = serializers.CharField(write_only=True, required=False)
    branch = serializers.PrimaryKeyRelatedField(queryset=Agent._meta.get_field('branch').related_model.objects.all(), required=False)
    unverified_collected_amount = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = ['agent_id', 'full_name', 'email', 'phone', 'area', 'id_proof', 'photo', 'status', 'is_demo', 'password', 'branch', 'unverified_collected_amount']
        read_only_fields = ['agent_id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        photo = getattr(instance, 'photo', None)
        if photo:
            path = photo.name
            if path.startswith('media/'):
                path = path[6:]
            data['photo'] = f'/media/{path}'
        else:
            data['photo'] = None
        id_proof = getattr(instance, 'id_proof', None)
        if id_proof:
            path = id_proof.name
            if path.startswith('media/'):
                path = path[6:]
            data['id_proof'] = f'/media/{path}'
        else:
            data['id_proof'] = None
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