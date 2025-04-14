"""
DEVELOPED AND MAINTAINED BY PRIYESH PANDEY. visit me at https://priyeshpandey.in/projects
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.urls import re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('cloudManager.urls'))
]


# Serve media files using re_path in production
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]