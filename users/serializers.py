from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # fields used by inventory serializer
        fields = ("id", "username", "email")

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # expose safe fields
        fields = ("id", "username", "email", "first_name", "last_name", "role", "is_active")
        read_only_fields = ("id", "is_active")

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "password2", "first_name", "last_name", "role")
        read_only_fields = ("id",)

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return data

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        # optionally set is_active=False and send email verification
        user.save()
        return user
