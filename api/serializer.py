from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from userauths.models import User, Profile
from api import models as api_models


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        """
        Customizes the token to include additional user information.
        """
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        token['full_name'] = user.full_name

        return token


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """
    # validators=[validate_password] is some rules to create a strong password
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True
    )

    class Meta:
        model = User
        fields = ['full_name', 'email', 'password', 'confirm_password']

    def validate(self, attrs):
        """
        Custom validation to ensure that the password and confirm_password match.
        """
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Password fields didn't match.")
        return attrs

    def create(self, validated_data):
        """
        Create a new user instance.
        """
        user = User.objects.create(
            full_name=validated_data['full_name'],
            email=validated_data['email'],
        )
        email_username, _ = user.email.split('@')  # '_' is used to ignore the second part of the split
        user.username = email_username
        user.set_password(validated_data['password'])  # Hash the password
        user.save()

        return user


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.
    """
    class Meta:  # It's just like a Django form
        model = User
        fields = '__all__'
        read_only_fields = ['id']


class ProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the Profile model.
    """
    class Meta:
        model = Profile
        fields = '__all__'
        read_only_fields = ['id', 'user']


class VariantItemSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.VariantItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(VariantItemSerializer, self).__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == 'POST':
            self.Meta.depth = 0  # related fields (like teacher, category) will just return their IDs.
        else:
            # (or more) → DRF will automatically serialize related models with their fields, nesting them deeper into the JSON output.
            self.Meta.depth = 3


class CompletedLessonSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.CompletedLesson
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super(CompletedLessonSerializer, self).__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == 'POST':
            self.Meta.depth = 0  # related fields (like teacher, category) will just return their IDs.
        else:
            # (or more) → DRF will automatically serialize related models with their fields, nesting them deeper into the JSON output.
            self.Meta.depth = 3
    


class Question_Answer_MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    profile = ProfileSerializer(many=False)

    class Meta:
        model = api_models.Question_Answer_Message
        fields = '__all__'


class Question_AnswerSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    messages = Question_Answer_MessageSerializer(many=True)
    profile = ProfileSerializer(many=False)

    class Meta:
        model = api_models.Question_Answer
        fields = '__all__'


class NoteSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """

    class Meta:
        model = api_models.Note
        fields = '__all__'


class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    profile = ProfileSerializer(many=False)

    class Meta:
        model = api_models.Review
        fields = '__all__'


class VariantSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    variant_item = VariantItemSerializer(many=True)

    class Meta:
        model = api_models.Variant
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(VariantSerializer, self).__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == 'POST':
            self.Meta.depth = 0  # related fields (like teacher, category) will just return their IDs.
        else:
            # (or more) → DRF will automatically serialize related models with their fields, nesting them deeper into the JSON output.
            self.Meta.depth = 3
    

class EnrolledCourseSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    lectures = VariantItemSerializer(many=True, read_only=True)
    completed_lessons = CompletedLessonSerializer(many=True, read_only=True)
    curriculum = VariantSerializer(many=True, read_only=True)
    note = NoteSerializer(many=True, read_only=True)
    question_answer = Question_AnswerSerializer(many=True, read_only=True)
    review = ReviewSerializer(many=False, read_only=True)

    class Meta:
        model = api_models.EnrolledCourse
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(EnrolledCourseSerializer, self).__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == 'POST':
            self.Meta.depth = 0
        else:
            self.Meta.depth = 3


class CourseSerializer(serializers.ModelSerializer):
    """
    Serializer for the Course model.
    """
    students = EnrolledCourseSerializer(many=True, required=False, read_only=True)
    curriculum = VariantSerializer(many=True, required=False, read_only=True)
    lectures = VariantItemSerializer(many=True, required=False, read_only=True)
    reviews = ReviewSerializer(many=True, required=False, read_only=True)

    class Meta:
        model = api_models.Course
        fields = [
            "id",
            "category",
            "teacher",
            "file",
            "image",
            "title",
            "description",
            "price",
            "language",
            "level",
            "platform_status",
            "teacher_status",
            "featured",
            "course_id",
            "slug",
            "date",
            "students",
            "curriculum",
            "lectures",
            "average_rating",
            "rating_count",
            "reviews",
        ]

    def __init__(self, *args, **kwargs):
        super(CourseSerializer, self).__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == 'POST':
            self.Meta.depth = 0  # related fields (like teacher, category) will just return their IDs.
        else:
            # (or more) → DRF will automatically serialize related models with their fields, nesting them deeper into the JSON output.
            self.Meta.depth = 3


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for the Category model.
    """

    class Meta:
        model = api_models.Category
        fields = [
            "title",
            "image",
            "active",
            "slug",
            "course_count",
        ]


class CartOrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.CartOrderItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(CartOrderItemSerializer, self).__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == 'POST':
            self.Meta.depth = 0  # related fields (like teacher, category) will just return their IDs.
        else:
            # (or more) → DRF will automatically serialize related models with their fields, nesting them deeper into the JSON output.
            self.Meta.depth = 3


class CartOrderSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    order_items = CartOrderItemSerializer(many=True)

    class Meta:
        model = api_models.CartOrder
        fields = '__all__'


class TeacherSerializer(serializers.ModelSerializer):
    """
    Serializer for the Teacher model.
    """
    student = CartOrderSerializer(many=True)
    courses = CourseSerializer(many=True)
    reviews = ReviewSerializer()

    class Meta:
        model = api_models.Teacher
        fields = [
            "user",
            "image",
            "full_name",
            "bio",
            "facebook",
            "twitter",
            "linkedin",
            "instagram",
            "about",
            "country",
            "student",
            "courses",
            "reviews",
        ]


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.Cart
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(CartSerializer, self).__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == 'POST':
            self.Meta.depth = 0  # related fields (like teacher, category) will just return their IDs.
        else:
            # (or more) → DRF will automatically serialize related models with their fields, nesting them deeper into the JSON output.
            self.Meta.depth = 3


class CertificateSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.Certificate
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.Notification
        fields = '__all__'


class CouponSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.Coupon
        fields = '__all__'


class WishlistSerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.Wishlist
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(WishlistSerializer, self).__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.method == 'POST':
            self.Meta.depth = 0  # related fields (like teacher, category) will just return their IDs.
        else:
            # (or more) → DRF will automatically serialize related models with their fields, nesting them deeper into the JSON output.
            self.Meta.depth = 3


class CountrySerializer(serializers.ModelSerializer):
    """
    Serializer for the Variant model.
    """
    class Meta:
        model = api_models.Country
        fields = '__all__'


class StudentSummarySerializer(serializers.Serializer):
    total_courses = serializers.IntegerField(default=0)
    completed_lessons = serializers.IntegerField(default=0)
    achieved_certificates = serializers.IntegerField(default=0)


class TeacherSummarySerializer(serializers.Serializer):
    total_courses = serializers.IntegerField(default=0)
    total_students = serializers.IntegerField(default=0)
    total_revenue = serializers.IntegerField(default=0)
    monthly_revenue = serializers.IntegerField(default=0)
