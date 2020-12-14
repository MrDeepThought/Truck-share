from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

# Register your models here.
# used to add custom user fields into admin user panel as well.
class UserAdmin(admin.ModelAdmin):
    model = User
    filter_horizontal = ('user_permissions', 'groups',)

admin.site.register(User,UserAdmin)
admin.site.register(City);
admin.site.register(Truck);
admin.site.register(Road);
admin.site.register(Order);
admin.site.register(Transporter);
admin.site.register(Manufacturer);
