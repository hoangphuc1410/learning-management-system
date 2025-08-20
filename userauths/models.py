from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save


class User(AbstractUser):
    """
    Custom user model that extends the default Django user model.
    """
    # Add any additional fields you want here
    username = models.CharField(unique=True, max_length=100)
    email = models.EmailField(unique=True, max_length=50)
    full_name = models.CharField(unique=True, max_length=100)
    otp = models.CharField(max_length=100, null=True, blank=True)
    refresh_token = models.CharField(max_length=1000, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        email_username = self.email.split('@')[0]
        if self.full_name == '' or self.full_name is None:
            self.full_name = email_username
        if self.username == '' or self.username is None:
            self.username = email_username
        super(User, self).save(*args, **kwargs)


class Profile(models.Model):
    """
    Profile model that extends the User model.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.FileField(upload_to='user_folder', default='default-user.png', null=True, blank=True)
    full_name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, null=True, blank=True)
    about = models.TextField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.full_name:
            return self.full_name
        return self.user.full_name

    def save(self, *args, **kwargs):
        if self.full_name == '' or self.full_name is None:
            self.full_name = self.user.username
        super(Profile, self).save(*args, **kwargs)
