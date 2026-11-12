"""API routes for the catalogue app.

The router creates one route for each action a ViewSet supports.
"""

from rest_framework.routers import DefaultRouter

from .views import AccessRequestViewSet, CodePackageViewSet

router = DefaultRouter()
router.register("packages", CodePackageViewSet, basename="package")
# basename is required: AccessRequestViewSet uses get_queryset() instead
# of a queryset attribute, so the router cannot derive a name.
router.register("requests", AccessRequestViewSet, basename="request")

urlpatterns = router.urls
