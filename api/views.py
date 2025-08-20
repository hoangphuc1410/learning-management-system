import random
from decimal import Decimal
import stripe
import requests  # get the item from the request data
from datetime import datetime, timedelta
from distutils.util import strtobool

from django.shortcuts import redirect
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import models
from django.db.models.functions import ExtractMonth

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.decorators import api_view

from api import serializer as api_serializers, models as api_models
from userauths.models import User, Profile


# Create your views here.

# get(): You expect one exact result and want an error if it's missing
# filter(): You expect zero or more results and want an empty list if it's missing

stripe.api_key = settings.STRIPE_SECRET_KEY
PAYPAL_CLIENT_ID = settings.PAYPAL_CLIENT_ID
PAYPAL_SECRET_ID = settings.PAYPAL_SECRET_ID


class MyTokenObtainPairView(TokenObtainPairView):
    """
    Custom view to obtain JWT tokens with additional user information.
    """
    serializer_class = api_serializers.MyTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """
    View to handle user registration.
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = api_serializers.RegisterSerializer


def generate_random_otp(length=7):
    """
    Generate a random 6-digit OTP.
    """
    otp = ''.join([str(random.randint(0, 9)) for _ in range(length)])
    return otp


class PasswordResetEmailVerifyAPIView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializers.UserSerializer

    def get_object(self):
        email = self.kwargs.get('email')

        user = User.objects.filter(email=email).first()
        if user:
            uuidb64 = user.pk
            refresh = RefreshToken.for_user(user)
            refresh_token = str(refresh.access_token)

            user.refresh_token = refresh_token
            user.otp = generate_random_otp()
            user.save()

            link = f"http://localhost:8000/create-new-password/?otp={user.otp}&uuidb64={uuidb64}&refresh_token={refresh_token}"

            context = {
                "link": link,
                "username": user.username,
            }
            subject = "Password Reset Email"
            text_body = render_to_string("email/password_reset.txt", context)
            html_body = render_to_string("email/password_reset.html", context)

            msg = EmailMultiAlternatives(
                subject=subject,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
                body=text_body,
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send()

        return user


class PasswordChangeAPIView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializers.UserSerializer

    def create(self, request, *args, **kwargs):
        payload = request.data

        otp = payload.get('otp')
        uuidb64 = payload.get('uuidb64')
        password = payload.get('password')

        user = User.objects.filter(pk=uuidb64, otp=otp).first()
        if user:
            user.set_password(password)
            user.otp = ""
            user.save()

            return Response({"message": "Password changed successfully"}, status=status.HTTP_201_CREATED)
        else:
            return Response({"message": "User Does Not Exists"}, status=status.HTTP_404_NOT_FOUND)


class ChangePasswordAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.UserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        user_id = request.data['user_id']
        old_password = request.data['old_password']
        new_password = request.data['new_password']
        user = User.objects.get(id=user_id)
        if user:
            if check_password(old_password, user.password):
                user.set_password(new_password)
                user.save()
                return Response({"message": "Password changed successfully", "icon": "success"})
            else:
                return Response({"message": "Old password is incorrect", "icon": "warning"})
        else:
            return Response({"message": "User does not exists.", "icon": "error"})  


class CategoryListAPIView(generics.ListAPIView):
    """
    View to list all categories.
    ListAPIView is used to get a list of objects.
    """
    queryset = api_models.Category.objects.filter(
        active=True)  # queryset: based on whatever model that you're trying to list
    serializer_class = api_serializers.CategorySerializer
    permission_classes = [AllowAny]


class CourseListAPIView(generics.ListAPIView):
    queryset = api_models.Course.objects.filter(
        platform_status="Published",
        teacher_status="Published",
    )
    serializer_class = api_serializers.CourseSerializer
    permission_classes = [AllowAny]


class CourseDetailAPIView(generics.RetrieveAPIView):
    """
    View to retrieve a single course by its ID.
    RetrieveAPIView is used to get a single object.
    """
    serializer_class = api_serializers.CourseSerializer
    permission_classes = [AllowAny]
    queryset = api_models.Course.objects.filter(
        platform_status="Published",
        teacher_status="Published",
    )

    def get_object(self):
        slug = self.kwargs.get('slug')
        try:
            course = api_models.Course.objects.get(slug=slug, platform_status="Published", teacher_status="Published")
        except api_models.Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=404)
        return course


class CartAPIView(generics.CreateAPIView):
    """
    View to handle adding items to the cart.
    """
    queryset = api_models.Cart.objects.all()
    serializer_class = api_serializers.CartSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        course_id = request.data['course_id']
        user_id = request.data['user_id']
        price = request.data['price']
        country_name = request.data['country']
        cart_id = request.data['cart_id']

        course = api_models.Course.objects.filter(id=course_id).first()
        if user_id != "undefined":
            user = User.objects.filter(id=user_id).first()
        else:
            user = None

        try:
            country_object = api_models.Country.objects.filter(name=country_name).first()
            country = country_object.name
        except:
            country_object = None
            country = "Unknown"

        if country_object:
            tax_rate = country_object.tax_price / 100
        else:
            tax_rate = 0

        cart = api_models.Cart.objects.filter(cart_id=cart_id, course=course).first()

        if cart:
            cart.course = course
            cart.user = user
            cart.price = price
            cart.tax_fee = Decimal(price) * Decimal(tax_rate)
            cart.country = country
            cart.cart_id = cart_id
            cart.total = Decimal(price) + cart.tax_fee
            cart.save()

            return Response(
                {"message": "Cart Updated successfully"},
                status=status.HTTP_200_OK
            )
        else:
            cart = api_models.Cart(
                course=course,
                user=user,
                price=price,
                tax_fee=Decimal(price) * Decimal(tax_rate),
                country=country,
                cart_id=cart_id,
                total=Decimal(price) + (Decimal(price) * Decimal(tax_rate))
            )

            cart.save()

            return Response(
                {"message": "Cart Created successfully"},
                status=status.HTTP_201_CREATED
            )


class CartListAPIView(generics.ListAPIView):
    """
    View to list all items in the cart for a specific user.
    """
    serializer_class = api_serializers.CartSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):  # The same thing as get_object() but for list views
        cart_id = self.kwargs.get('cart_id')
        queryset = api_models.Cart.objects.filter(cart_id=cart_id)
        return queryset


class CartItemDeleteAPIView(generics.DestroyAPIView):
    """
    View to delete an item from the cart.
    """
    serializer_class = api_serializers.CartSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        cart_id = self.kwargs.get('cart_id')
        item_id = self.kwargs.get('item_id')
        cart_item = api_models.Cart.objects.filter(cart_id=cart_id, id=item_id).first()

        return cart_item


class CartStatisticsAPIView(generics.RetrieveAPIView):
    serializer_class = api_serializers.CartSerializer
    permission_classes = [AllowAny]
    lookup_field = 'cart_id'  # Using 'cart_id' instead of 'pk'

    def get_queryset(self):
        cart_id = self.kwargs.get('cart_id')
        queryset = api_models.Cart.objects.filter(cart_id=cart_id)

        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        total_price = 0.00
        total_tax = 0.00
        total = 0.00

        for cart_item in queryset:
            total_price += float(cart_item.price)
            total_tax += float(cart_item.tax_fee)
            total += round(float(cart_item.total), 2)

        data = {
            "price": total_price,
            "tax": total_tax,
            "total": total
        }

        return Response(data, status=status.HTTP_200_OK)


class CreateOrderAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.CartOrderSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        full_name = request.data['full_name']
        email = request.data['email']
        country = request.data['country']
        cart_id = request.data['cart_id']
        user_id = request.data['user_id']

        if user_id != 0:
            user = User.objects.get(id=user_id)
        else:
            user = None

        cart_items = api_models.Cart.objects.filter(cart_id=cart_id)

        price = Decimal(0.00)
        tax = Decimal(0.00)
        initial_total = Decimal(0.00)
        total = Decimal(0.00)

        order = api_models.CartOrder.objects.create(
            full_name=full_name,
            email=email,
            country=country,
            student=user,
        )

        for cart in cart_items:
            api_models.CartOrderItem.objects.create(
                order=order,
                course=cart.course,
                price=cart.price,
                tax_fee=cart.tax_fee,
                total=cart.total,
                initial_total=cart.total,
                teacher=cart.course.teacher,
            )

            price += Decimal(cart.price)
            tax += Decimal(cart.tax_fee)
            initial_total += Decimal(cart.total)
            total += Decimal(cart.total)

            order.teacher.add(cart.course.teacher)

        order.sub_total = price
        order.tax_fee = tax
        order.initial_total = initial_total
        order.total = total

        order.save()

        return Response(
            {"message": "Order Created Successfully", "order_oid": order.oid},
            status=status.HTTP_201_CREATED
        )


class CheckoutAPIView(generics.RetrieveAPIView):
    serializer_class = api_serializers.CartOrderSerializer
    permission_classes = [AllowAny]
    queryset = api_models.CartOrder.objects.all()
    lookup_field = 'oid'


class CouponApplyAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.CouponSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        order_id = request.data['order_oid']
        coupon_code = request.data['coupon_code']

        cart_order = api_models.CartOrder.objects.get(oid=order_id)
        coupon = api_models.Coupon.objects.get(code=coupon_code, active=True)

        if coupon:
            order_items = api_models.CartOrderItem.objects.filter(order=cart_order, teacher=coupon.teacher)
            for order in order_items:
                if coupon not in order.coupons.all():

                    discount = order.total * coupon.discount / 100
                    order.total -= discount
                    order.price -= discount
                    order.saved -= discount
                    order.applied_coupon = True
                    order.coupons.add(coupon)

                    cart_order.coupons.add(coupon)
                    cart_order.total -= discount
                    cart_order.sub_total -= discount
                    cart_order.saved += discount

                    order.save()
                    cart_order.save()
                    coupon.used_by.add(order.student)

                    return Response(
                        {"message": "Coupon Found and Activated", "icon": "success"},
                        status=status.HTTP_201_CREATED
                    )
                else:
                    return Response(
                        {"message": "Coupon Already Applied", "icon": "warning"},
                        status=status.HTTP_200_OK
                    )
        else:
            return Response(
                {"message": "Coupon Not Found", "icon": "error"},
                status=status.HTTP_404_NOT_FOUND
            )


class StripeCheckoutAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.CartOrderSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        order_id = self.kwargs['order_id']
        order = api_models.CartOrder.objects.get(oid=order_id)

        if not order:
            return Response({"message": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            checkout_session = stripe.checkout.Session.create(
                customer_email=order.email,
                payment_method_types=['card'],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": order.full_name,
                            },
                            "unit_amount": int(order.total * 100),
                        },
                        "quantity": 1
                    }
                ],
                mode="payment",
                success_url=settings.FRONTEND_SITE_URL
                            + 'payment-success/' + order.oid + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=settings.FRONTEND_SITE_URL + 'payment-failed/',
            )
            print("checkout_session====\n", checkout_session)
            order.stripe_session_id = checkout_session.id
            return redirect(checkout_session.url)
        except stripe.error.StripeError as e:
            return Response({"message": f"Something went wrong when trying to make payment. Error: {str(e)}"})


def get_access_token(client_id, secret_key):
    token_url = "https://api.sandbox.paypal.com/v1/oauth2/token"
    data = {
        'grant_type': 'client_credentials'
    }
    auth = (client_id, secret_key)
    response = requests.post(token_url, data=data, auth=auth)

    if response.status_code == 200:
        print("Access ==== \n", response.json()['access_token'])
        return response.json()['access_token']
    else:
        raise Exception(f"Failed to get access token from paypal {response.status_code}")


class PaymentSuccessAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.CartOrderSerializer
    permission_classes = [AllowAny]
    queryset = api_models.CartOrder.objects.all()

    def create(self, request, *args, **kwargs):
        order_oid = request.data['order_oid']
        session_id = request.data['session_id']
        paypal_order_id = request.data['paypal_order_id']

        order = api_models.CartOrder.objects.get(oid=order_oid)
        order_items = api_models.CartOrderItem.objects.filter(order=order)

        # Paypal Payment success
        if paypal_order_id != "null":
            paypal_api_url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{paypal_order_id}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {get_access_token(PAYPAL_CLIENT_ID, PAYPAL_SECRET_ID)}"
            }
            response = requests.get(paypal_api_url, headers=headers)
            if response.status_code == 200:
                paypal_order_data = response.json()
                paypal_payment_status = paypal_order_data['status']
                if paypal_payment_status == "COMPLETED":
                    if order.payment_status == "Processing":
                        order.payment_status = "Paid"
                        order.save()

                        api_models.Notification.objects.create(
                            user=order.student, order=order, type="Course Enrollment Completed"
                        )
                        for order_item in order_items:
                            api_models.Notification.objects.create(
                                teacher=order_item.course.teacher,
                                order=order,
                                order_item=order_item,
                                type="New Order"
                            )
                            api_models.EnrolledCourse.objects.create(
                                course=order_item.course,
                                user=order.student,
                                teacher=order_item.teacher,
                                ordre_item=order_item
                            )
                        return Response({"messages": "Payment Successful"})
                    else:
                        return Response({"message": "Already Paid"})
                else:
                    return Response({"messages": "Payment Failed"})
            else:
                return Response({"message": "PayPal Error Occurred"})

        # Stripe Payment success
        if session_id != "null":
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                if order.payment_status == "Processing":
                    order.payment_status = "Paid"
                    order.save()

                    api_models.Notification.objects.create(
                        user=order.student, order=order, type="Course Enrollment Completed"
                    )
                    for order_item in order_items:
                        api_models.Notification.objects.create(
                            teacher=order_item.course.teacher,
                            order=order,
                            order_item=order_item,
                            type="New Order"
                        )
                        api_models.EnrolledCourse.objects.create(
                            course=order_item.course,
                            user=order.student,
                            teacher=order_item.teacher,
                            ordre_item=order_item
                        )

                    return Response({"messages": "Payment Successful"})
                else:
                    return Response({"message": "Already Paid"})
            else:
                return Response({"messages": "Payment Failed"})


class SearchCourseAPIView(generics.ListAPIView):
    serializer_class = api_serializers.CourseSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        query = self.request.GET.get('query')
        return api_models.Course.objects.filter(
            title__icontains=query,
            platform_status="Published",
            teacher_status="Published"
        )

class StudentSummaryAPIView(generics.ListAPIView):
    serializer_class = api_serializers.StudentSummarySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)

        total_courses = api_models.EnrolledCourse.objects.filter(user=user).count()
        completed_lessons = api_models.CompletedLesson.objects.filter(user=user).count()
        achieved_certificates = api_models.Certificate.objects.filter(user=user).count()

        return [{
            "total_courses": total_courses,
            "completed_lessons": completed_lessons,
            "achieved_certificates": achieved_certificates,
        }]
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True) # grab the serializer in serializer_class

        return Response(serializer.data)


class StudentCourseAPIView(generics.ListAPIView):
    serializer_class = api_serializers.EnrolledCourseSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        return api_models.EnrolledCourse.objects.filter(user=user)


class StudentDetailAPIView(generics.RetrieveAPIView):
    serializer_class = api_serializers.EnrolledCourseSerializer
    permission_classes = [AllowAny]
    lookup_field = "enrolled_id"

    def get_object(self):
        user_id = self.kwargs['user_id']
        enrolled_id = self.kwargs['enrollment_id']

        user = User.objects.get(id=user_id)
        enrollment = api_models.EnrolledCourse.objects.get(enrolled_id=enrolled_id, user=user)

        return enrollment


class StudentCourseCompletedCreateAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.CompletedLessonSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        user_id = request.data['user_id']
        course_id = request.data['course_id']
        variant_item_id = request.data['variant_item_id']

        user = User.objects.get(id=user_id)
        course = api_models.Course.objects.get(id=course_id)
        variant_item = api_models.VariantItem.objects.get(variant_item_id=variant_item_id)

        completed_lessons = api_models.CompletedLesson.objects.filter(
            user=user, course=course, variant_item=variant_item
        ).first()

        if completed_lessons:
            completed_lessons.delete()
            return Response({"message": "Course marked as not completed"})
        else:
            api_models.CompletedLesson.objects.create(
                user=user, course=course, variant_item=variant_item
            )
            return Response({"message": "Course marked as completed"})


class StudentNoteCreateAPIView(generics.ListCreateAPIView):
    serializer_class = api_serializers.NoteSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        enrollment_id = self.kwargs['enrollment_id']

        user = User.objects.get(id=user_id)
        enrollmed = api_models.EnrolledCourse.objects.get(enrolled_id=enrollment_id)

        return api_models.Note.objects.get(user=user, course=enrollmed.course)

    def create(self, request, *args, **kwargs):
        user_id = request.data['user_id']
        enrollment_id = request.data['enrollment_id']
        title = request.data['title']
        note = request.data['note']

        user = User.objects.get(id=user_id)
        enrollmed = api_models.EnrolledCourse.objects.get(enrolled_id=enrollment_id)

        api_models.Note.objects.create(user=user, course=enrollmed.course, title=title, note=note)

        return Response({"message": "Note created successfully"}, status=status.HTTP_201_CREATED)


class StudentDetailNoteAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializers.NoteSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        user_id = self.kwargs['user_id']
        enrollment_id = self.kwargs['enrollment_id']
        note_id = self.kwargs['note_id']

        user = User.objects.get(id=user_id)
        enrolled = api_models.EnrolledCourse.objects.get(enrolled_id=enrollment_id)
        note = api_models.Note.objects.get(user=user, course=enrolled.course, id=note_id)

        return note


class StudentRateCourseCreateAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.ReviewSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        user_id = request.data['user_id']
        course_id = request.data['course_id']
        rating = request.data['rating']
        review = request.data['review']

        user = User.objects.get(id=user_id)
        course = api_models.Course.objects.get(id=course_id)

        api_models.Review.objects.create(
            user=user,
            course=course,
            review=review,
            rating=rating,
            active=True,
        )

        return Response({"message": "Review created successfully"}, status=status.HTTP_201_CREATED)


class StudentRateCourseUpdateAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = api_serializers.ReviewSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        user_id = self.kwargs['user_id']
        review_id = self.kwargs['review_id']

        user = User.objects.get(id=user_id)
        return api_models.Review.objects.get(id=review_id, user=user)


class StudentWishListListAPIView(generics.ListCreateAPIView):
    serializer_class = api_serializers.WishlistSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']

        user = User.objects.get(id=user_id)

        return api_models.Wishlist.objects.filter(user=user)

    def create(self, request, *args, **kwargs):
        user_id = request.data['user_id']
        course_id = request.data['course_id']

        user = User.objects.get(id=user_id)
        course = api_models.Course.objects.get(id=course_id)
        wishlist = api_models.Wishlist.objects.filter(user=user, course=course).first()

        if wishlist:
            wishlist.delete()
            return Response({"message": "Wishlist Deleted"}, status=status.HTTP_200_OK)
        else:
            api_models.Wishlist.objects.create(
                user=user,
                course=course
            )
            return Response({"message": "Wishlist created successfully"}, status=status.HTTP_201_CREATED)


class QuestionAnswerListAPIView(generics.ListCreateAPIView):
    serializer_class = api_serializers.Question_AnswerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        course_id = self.kwargs['course_id']
        course = api_models.Course.objects.get(id=course_id)

        return api_models.Question_Answer.objects.filter(course=course)
    
    def create(self, request, *args, **kwargs):
        course_id = request.data['course_id']
        user_id = request.data['user_id']
        title = request.data['title']
        message = request.data['message']

        user = User.objects.get(id=user_id)
        course = api_models.Course.objects.get(id=course_id)

        question = api_models.Question_Answer.objects.create(
            course=course,
            user=user,
            title=title
        )

        api_models.Question_Answer_Message.objects.create(
            course=course,
            user=user,
            message=message,
            question=question,
        )

        return Response({"message": "Group conversation Started"}, status=status.HTTP_201_CREATED)
    

class QuestionAnswerMssageSendAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.Question_Answer_MessageSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        course_id = request.data['course_id']
        user_id = request.data['user_id']
        qa_id = request.data['qa_id']
        message = request.data['message']

        user = User.objects.get(id=user_id)
        course = api_models.Course.objects.get(id=course_id)
        question = api_models.Question_Answer.objects.get(qa_id=qa_id)
        api_models.Question_Answer_Message.objects.create(
            course=course,
            user=user,
            message=message,
            question=question
        )

        question_serializer = api_serializers.Question_AnswerSerializer(question)

        return Response({"message": "Message Sent", "question": question_serializer.data})


class ProfileAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = api_serializers.ProfileSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        try:
            user_id = self.kwargs['user_id']
            user = User.objects.get(id=user_id)
            return Profile.objects.get(user=user)
        except:
            return None


class TeacherSummaryAPIView(generics.ListAPIView):
    serializer_class = api_serializers.TeacherSummarySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        one_month_ago = datetime.today() - timedelta(days=28)

        total_courses = api_models.Course.objects.filter(teacher=teacher).count()
        # order__payment_status meaning is directly to field payment_status on model order
        total_revenue = api_models.CartOrderItem.objects.filter(teacher=teacher, order__payment_status="Paid").aggregate(total_revenue=models.Sum("price"))["total_revenue"] or 0
        monthly_revenue = api_models.CartOrderItem.objects.filter(teacher=teacher, order__payment_status="Paid", date__gte=one_month_ago).aggregate(total_revenue=models.Sum("price"))["total_revenue"] or 0

        enrolled_courses = api_models.EnrolledCourse.objects.filter(teacher=teacher)
        unique_student_id = set()
        students = []

        for course in enrolled_courses:
            if course.user_id not in unique_student_id:
                user = User.objects.get(id=course.user_id)
                student = {
                    "full_name": user.profile.full_name,
                    "image": user.profile.image.url,
                    "country": user.profile.country,
                    "date": course.date,
                }   

                students.append(student)
                unique_student_id.add(course.user_id)

        return [{
            "total_courses": total_courses,
            "total_students": len(students),
            "total_revenue": total_revenue,
            "monthly_revenue": monthly_revenue,
        }]
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True) # grab the serializer in serializer_class

        return Response(serializer.data)


class TeacherCourseAPIView(generics.ListAPIView):
    serializer_class = api_serializers.CourseSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.Course.objects.filter(teacher=teacher)


class TeacherReviewListAPIView(generics.ListAPIView):
    serializer_class = api_serializers.ReviewSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.Review.objects.filter(course__teacher=teacher)


class TeacherReviewDetailAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = api_serializers.ReviewSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        teacher_id = self.kwargs['teacher_id']
        review_id = self.kwargs['review_id']

        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.Review.objects.get(course__teacher=teacher, id=review_id)


class TeacherStudentListAPIView(viewsets.ViewSet):
    # Write own custom query
    def list(self, request, teacher_id=None):
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        enrolled_courses = api_models.EnrolledCourse.objects.filter(teacher=teacher)
        unique_student_id = set()
        students = []

        for course in enrolled_courses:
            if course.user_id not in unique_student_id:
                user = User.objects.get(id=course.user_id)
                student = {
                    "full_name": user.profile.full_name,
                    "image": user.profile.image.url,
                    "country": user.profile.country,
                    "date": course.date,
                }   

                students.append(student)
                unique_student_id.add(course.user_id)

        return Response(students)


@api_view(["GET"])
def TeacherAllMonthEarningAPIView(request, teacher_id):
    teacher = api_models.Teacher.objects.get(id=teacher_id)

    monthly_earning_tracker = api_models.CartOrderItem.objects.filter(teacher=teacher, order__payment_status="Paid").annotate(month=ExtractMonth("date")).values("month").annotate(total_earning=models.Sum("price")).order_by("month")

    return Response(monthly_earning_tracker)


class TeacherBestSellingCourseAPIView(viewsets.ViewSet):
    def list(self, request, teacher_id=None):
        teacher = api_models.Teacher.objects.get(id=teacher_id)
        courses_with_total_price = []
        courses = api_models.Course.objects.filter(teacher=teacher) 

        for course in courses:
            revenue = course.enrolledcourse_set.aggregate(total_price=models.Sum('order_item__price'))['total_price'] or 0
            sales = course.enrolledcourse_set.count()

            courses_with_total_price.append({
                'course_image': course.image.url,
                "course_title": course.title,
                "revenue": revenue,
                "sales": sales
            })

        return Response(courses_with_total_price)
    

class TeacherCourseOrdersListAPIView(generics.ListAPIView):
    serializer_class = api_serializers.CartOrderItemSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.CartOrderItem.objects.filter(teacher=teacher)


class TeacherQuestionAnswerListAPIView(generics.ListAPIView):
    serializer_class = api_serializers.Question_AnswerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.Question_Answer.objects.filter(course__teacher=teacher)


class TeacherCouponListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = api_serializers.CouponSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.Coupon.objects.filter(teacher=teacher)
    

class TeacherCouponDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializers.CouponSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        teacher_id = self.kwargs['teacher_id']
        coupon_id = self.kwargs['coupon_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.Coupon.objects.get(teacher=teacher, id=coupon_id)


class TeacherNotificationListAPIView(generics.ListAPIView):
    serializer_class = api_serializers.NoteSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.Notification.objects.filter(teacher=teacher, seen=False)

class TeacherNotificationDetailAPIView(generics.RetrieveDestroyAPIView):
    serializer_class = api_serializers.NoteSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        teacher_id = self.kwargs['teacher_id']
        noti_id = self.kwargs['note_id']
        teacher = api_models.Teacher.objects.get(id=teacher_id)

        return api_models.Notification.objects.get(teacher=teacher, id=noti_id)


class CourseCreateAPIView(generics.CreateAPIView):
    serializer_class = api_serializers.CourseSerializer
    permission_classes = [AllowAny]
    queryset = api_models.Course.objects.all()

    def perform_create(self, serializer):
        serializer.is_valid(raise_xception=True)
        course_instance = serializer.save()

        variant_data = []
        for key, value in self.request.data.items():
            if key.startswith('variant') and '[variant_title]' in key:
                index = key.split('[')[1].split(']')[0]
                title = value

                variant_data = {'title': title}
                item_data_list = []
                current_item = {}

                for item_key, item_value in self.request.data.items():
                    if f'variants[{index}][items]' in item_key:
                        field_name = item_key.split('[')[-1].split(']')[0]
                        if field_name == 'title':
                            if current_item:
                                item_data_list.append(current_item)
                            current_item = {}
                        
                        current_item.update({field_name: item_value})
                
                if current_item:
                    item_data_list.append(current_item)
                
                variant_data.append({'variant_data': variant_data, 'variant_item_data': item_data_list})
        
        for data_entry in variant_data:
            variant = api_models.Variant.objects.create(title=data_entry['variant_data']['title'], course=course_instance)

            for item_data in data_entry['variant_item_data']:
                preview_value = item_data.get("preview")
                preview = bool(strtobool(str(preview_value))) if preview_value is not None else False

                api_models.VariantItem.objects.create(
                    variant=variant,
                    title=item_data.get('title'),
                    description=item_data.get('description'),
                    file=item_data.get('file'),
                    preview=preview
                )

    def save_nested_data(self, course_instance, serializer_class, data):
        serializer = serializer_class(data=data, many=True, context={"course_instance": course_instance})
        serializer.is_valid(raise_exception=True)
        serializer.save(course=course_instance)
