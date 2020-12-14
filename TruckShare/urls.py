from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("register", views.register, name="register"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("trucks/add_trucks/<int:transporterId>", views.add_trucks, name="addTrucks"),
    path("trucks", views.trucks, name="trucks"),
    path("profile/<int:transporterId>", views.transporter_profile, name="transporterProfile"),
    path("compare", views.compare, name="compare"),
    path("options", views.options, name="options"),
]
