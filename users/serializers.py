# users/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class SimpleUserSerializer(serializers.ModelSerializer):
    """Lightweight serializer used by other apps (e.g., notifications)."""
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email", "role")


class UserSerializer(serializers.ModelSerializer):
    """
    Full user serializer for admin CRUD.
    - password is write_only and handled with set_password
    - role must be set carefully by admin
    """
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    is_superuser = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
            "password",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined")

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        # create user (admin is calling this)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        else:
            user.set_unusable_password()
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        username = validated_data.get("username", None)
        if username is not None:
            instance.username = username

        instance.email = validated_data.get("email", instance.email)
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.role = validated_data.get("role", instance.role)
        instance.is_active = validated_data.get("is_active", instance.is_active)
        instance.is_staff = validated_data.get("is_staff", instance.is_staff)
        instance.is_superuser = validated_data.get("is_superuser", instance.is_superuser)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Admin-side user creation serializer.
    Not exposed to public — admin uses this to create users.
    """
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
        # username can be optional; if missing, set from email's local-part
        username = validated_data.get("username")
        if not username and validated_data.get("email"):
            validated_data["username"] = validated_data["email"].split("@")[0]
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
