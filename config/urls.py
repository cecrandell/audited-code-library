"""Root URL configuration.

Sends /admin/ to the Django admin, /api/ to the catalogue API, and
/api-auth/ to the login pages for the browsable API.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("catalogue.urls")),
    path("api-auth/", include("rest_framework.urls")),
]
