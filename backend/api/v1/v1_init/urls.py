from django.urls import re_path
from . import views

urlpatterns = [
    re_path(
        r"^(?P<version>(v1))/health/check",
        views.health_check,
        name="health_check",
    ),
]
