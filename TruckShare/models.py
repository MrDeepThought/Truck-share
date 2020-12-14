from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class City(models.Model):

    name = models.CharField(max_length=50);
    state = models.CharField(max_length=50);

    def __str__(self):
        return self.name;

class Road(models.Model):

    connection = models.ManyToManyField(City, related_name='roads');
    distance = models.IntegerField(null=True);
    speedCap = models.FloatField(null=True);
    tollTax = models.IntegerField(default=0);


class User(AbstractUser):
    companyName = models.CharField(max_length=100);
    phoneNo = models.CharField(max_length=10);
    is_manufacturer = models.BooleanField(default=False);
    is_transporter = models.BooleanField(default=False);

class Manufacturer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE);
    goodsTypes = models.CharField(max_length=100);
    location = models.ForeignKey(City, on_delete=models.CASCADE, related_name='manfacturers');

    def __str__(self):
        return self.user.companyName;

class Transporter(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE);
    laborCost = models.IntegerField(null=True);
    location = models.ForeignKey(City, on_delete=models.CASCADE, related_name='transporters');
    numTrucksOwned = models.IntegerField(default=0);

    def __str__(self):
        return self.user.companyName;

class Truck(models.Model):

    TYPES = (
        ('SMT1','Small Moving Truck-1'),
        ('SMT2','Small Moving Truck-2'),
        ('LMT1','Large Moving Truck-1'),
        ('LMT2','Large Moving Truck-2'),
    );

    truckType = models.CharField(max_length=4, choices=TYPES, default='SMT1')
    maxSpeed = models.IntegerField(null=True);
    mileage = models.FloatField(null=True);
    volumeCap = models.IntegerField(null=True);
    weightCap = models.IntegerField(null=True);
    volumeFilled = models.IntegerField(null=True);
    weightFilled = models.IntegerField(null=True);
    costFact1 = models.IntegerField(null=True);
    costFact2 = models.IntegerField(null=True);
    availability = models.BooleanField(default=True);
    booked = models.BooleanField(default=False);
    owner = models.ForeignKey(Transporter, related_name='ownedTrucks', on_delete=models.CASCADE, null=True);
    parkedAt = models.ForeignKey(Transporter,related_name='parkedTrucks', on_delete=models.CASCADE, null=True);

    def __str__(self):
        return f'{self.truckType} : {self.owner.user.companyName}';

class OrderDate(models.Model):
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.CASCADE);
    date = models.DateTimeField(null=True);

class Order(models.Model):
    statuses = (
        ('not accepted', 'Not Accpeted'),
        ('pending', 'Pending'),
        ('on delivery', 'On delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    );

    status = models.CharField(max_length=12, choices=statuses, default='not accepted');
    departure = models.ManyToManyField(OrderDate, related_name="dateDepartures");
    delivery = models.ManyToManyField(OrderDate, related_name="dateDeliveries");
    source = models.ForeignKey(City, null=True, on_delete=models.CASCADE, related_name='sourceOrders');
    destination = models.ForeignKey(City, null=True, on_delete=models.CASCADE, related_name='destinationOrders');
    #TimeFlexibility = models.BooleanField(default=True); future improvements.
    customers = models.ManyToManyField(Manufacturer, related_name='orders');
    transporter = models.ForeignKey(Transporter, on_delete=models.CASCADE, related_name='invoices');
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, related_name='truckOrders');
    travellingRoute = models.ManyToManyField(Road, related_name='roadOrders')
    payment = models.FloatField(null=True);
    weightOccupied = models.IntegerField(null=True);
    volumeOccupied = models.IntegerField(null=True);
