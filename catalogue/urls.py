from rest_framework.routers import DefaultRouter

from .views import AccessRequestViewSet, CodePackageViewSet

router = DefaultRouter()
router.register("packages", CodePackageViewSet, basename="package")
router.register("requests", AccessRequestViewSet, basename="request")

urlpatterns = router.urls
