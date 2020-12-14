from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.shortcuts import HttpResponseRedirect, HttpResponse, render
#from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import *
import datetime

FUELCOST = 80;
#************Utility functions************#
def create_date_object(pickupDate):
    rmvChars = '-T:';
    date = []
    for char in pickupDate:
        if char in rmvChars:
            date.append(' ');
        else:
            date.append(char);
    date = ''.join(date);
    date = [x for x in map(int,date.split())];
    return datetime.datetime(year=date[0],month=date[1],day=date[2],hour=date[3],minute=date[4]);

def search_road(city1,city2):
    roads = list(city1.roads.all());
    for road in roads:
        connect = list(road.connection.all());
        if city2 in connect:
            return road;

def calculate_truck_cost(truck,distanceTravel,totalToll,weightOcc,volumeOcc,share=False,numCustomers=0):
    #cost = fuelcost + laborcost + wt/volcost + tolltax
    global FUELCOST
    stdDensity = truck.owner.weightCap/truck.owner.volumeCap;
    goodsDensity = weightOcc/volumeOcc;
    mileage = truck.mileage;

    spaceCost = 0;
    if goodsDensity > stdDensity:
        spaceCost = weightOcc*truck.costFact1;
    else:
        spaceCost = volumeOcc*truck.costFact2;
    fuelCost = int((distanceTravel/mileage)*FUELCOST);
    laborCost = truck.owner.laborCost;
    tollCost = totalToll;
    totalCost = fuelCost + laborCost + tollCost + spaceCost;

    if not share:
        return totalCost;
    else:
        return int(totalCost/numCustomers);

def calculate_ETA(travelTime,departure):
    departureDay = departure.day;
    departureHrs = departure.hour;
    if travelTime > 24:
        days = travelTime%24;
        hours = travelTime - 24*(travelTime//24);

        finalHrs = departureHrs + hours;

        if finalHrs > 24:
            departureDay += (days + finalHrs%24);
            departureHrs += (finalHrs - 24*(finalHrs//24));
    else:
        finalHrs = departureHrs + travelTime;

        if finalHrs > 24:
            departureDay += (finalHrs%24);
            departureHrs += (finalHrs - 24*(finalHrs//24));

    return datetime.datetime(year=departure.year,month=departure.month,day=departureDay,hour=departureHrs,minute=departure.minute);

def create_free_orders(freeTruckList,params):
    orderList = []
    for truck in freeTruckList:
        sourceCity = City.objects.get(name=params['source']);
        destinationCity = City.objects.get(name=params['destination']);
        stateCenter1 = City.objects.get(name=f'State-Center {sourceCity.state}');
        stateCenter2 = City.objects.get(name=f'State-Center {destinationCity.state}');
        transporterCity = City.objects.get(name=truck.owner.location);

        travellingRoute = [];
        distanceTravel = 0;
        totalToll = 0;
        travelTime = 0;
        departure = params['departure'];

        if transporterCity != sourceCity:
            road = search_road(transporterCity,sourceCity);
            travellingRoute.append(road);
            distanceTravel+=road.distance;
            totalToll+=road.tollTax;

        cities = [sourceCity,stateCenter1,stateCenter2,destinationCity];
        for i in range(0,len(cities)-1):
            road = search_road(cities[i],cities[i+1]);
            travellingRoute.append(road);
            distanceTravel+=road.distance;
            totalToll+=road.tollTax;
            travelTime+=int(road.distance/min(road.speedCap,truck.maxSpeed));

        payment = calculate_truck_cost(truck,distanceTravel,totalToll,params['weightOccupied'],params['volumeOccupied']);
        truck.weightFilled = params['weightOccupied'];
        truck.volumeFilled = params['volumeOccupied'];
        truck.booked = True;
        truck.save()
        delivery = calculate_ETA(travelTime,departure);
        toPark = None;
        if truck.toPark == truck.owner:
            truck.toPark = destinationCity.transporters.first();
        else:
            truck.toPark = truck.owner;
        truck.save();

        order = Order(
            transporter=truck.owner,
            truck=truck,
            payment=payment,
            weightOccupied=params['weightOccupied'],
            volumeOccupied=params['volumeOccupied'],
            status = 'pending'
        );
        departureDate = OrderDate(manufacturer=params['customer'],date=departure);
        deliveryDate = OrderDate(manufacturer=params['customer'],date=delivery);
        departureDate.save();
        deliveryDate.save()
        order.departure.add(departureDate);
        order.delivery.add(deliveryDate);
        order.customers.add(params['customer']);
        for road in travellingRoute:
            order.travellingRoute.add(road);
        order.save();
        orderList.append(order);

    return orderList;

def change_delivery_dates(orderCustomers,order,addTravelTime):
    for customer in orderCustomers:
        departureDates = list(order.departure.all());
        deliveryDates = list(order.delivery.all());
        dates = zip(departureDates,deliveryDates)
        customerDelivery,customerDeparture = None,None;
        for departureDate,deliveryDate in dates:
            if departureDate.manufacturer == customer:
                customerDeparture = departureDate.date;
            if deliveryDate.manufacturer == customer:
                customerDelivery = deliveryDate.date;
            if customerDelivery is not None and customerDeparture is not None:
                break;
        prevETA = int(str(customerDelivery-customerDeparture).split(':')[0]);
        newTravelTime = prevETA + addTravelTime;
        newDelivery = calculate_ETA(newTravelTime,customerDeparture);
        newDeliveryDate = OrderDate(manufacturer=customer,date=newDelivery);
        date = order.delivery.remove(customerDelivery);
        date.delete();
        order.delivery.add(newDeliveryDate);
        order.save();

def create_share_orders(shareTruckList,params):
    orderList = []
    for truck in freeTruckList:
        sourceCity = City.objects.get(name=params['source']);
        destinationCity = City.objects.get(name=params['destination']);
        stateCenter1 = City.objects.get(name=f'State-Center {sourceCity.state}');
        stateCenter2 = City.objects.get(name=f'State-Center {destinationCity.state}');

        truckOrders = list(truck.truckOrders.all());
        order = None;
        for truckOrder in truckOrders:
            if truckOrder.status == "pending":
                order = truckOrder;
                break;
        orderCustomers = list(order.customers.all());
        lastCustomer = order.customers.last();
        lastSourceCity = City.objects.get(name=lastCustomer.location);
        lastDestinationCity = City.objects.get(name=order.destination);
        numCustomers = len(orderCustomers)+1;

        distanceTravel = 0;
        totalToll = 0;
        travelTime = 0;

        #change travellingRoute
        addRoad1,addRoad2,addRoad3,removeRoad = None,None,None,None;
        if sourceCity != lastSourceCity:
            removeRoad = search_road(lastSourceCity,stateCenter1);  #road between last added customers source city-stateCenter(source)
            addRoad1 = search_road(lastSourceCity,sourceCity);  #road between last added source-new source city
            addRoad2 = search_road(sourceCity,stateCenter1);    #road between new source city-stateCenter(source)
            order.travellingRoute.remove(removeRoad);
            order.travellingRoute.add(addRoad1);
            order.travellingRoute.add(addRoad2);
        if lastDestinationCity != destinationCity:
            addRoad3 = search_road(lastDestinationCity,destinationCity);    #road between last destination city-new destination city
            order.travellingRoute.add(addRoad3);

        for road in list(order.travellingRoute.all()):
            if addRoad1 is not None and addRoad1 == road:
                continue;
            distanceTravel+=(road.distance);
            travelTime+=(road.distance//min(road.speedCap,truck.maxSpeed));
            totalToll+=(road.tollTax);

        #change travelTime of previous customers
        if removeRoad is not None:
            newPickupTime1 = addRoad1.distance//min(addRoad1.speedCap,truck.maxSpeed);
            newPickupTime2 = addRoad2.distance//min(addRoad2.speedCap,truck.maxSpeed);
            removePickupTime = removeRoad.distance//min(removeRoad.speedCap,truck.maxSpeed);
            departureDiffTime = str(params['departure'] - order.departure.last().date).spit(':')[0];

            #if travel time from lastcustomer to newcustomer is less than or greater than departure time difference between them.
            if departureDiffTime.hour > newPickupTime1:
                addTravelTime = int(departureDiffTime) - removePickupTime + newPickupTime2;
                #change delivery time of previous customers
                change_delivery_dates(orderCustomers,order,addTravelTime);


            else:
                addTravelTime = newPickupTime1 - removePickupTime + newPickupTime2;
                #change departure time of new customer and delivery time of last previous customers
                #first change delivery time of previous customers
                change_delivery_dates(orderCustomers,order,addTravelTime);

                #second change departure date of new customer to travelTime between last and new customer.
                params['departure'] = calculate_ETA(newPickupTime1,params['departure']);

        else:
            departureDiffTime = str(params['departure'] - order.departure.last().date).split(':')[0];
            addTravelTime = int(departureDiffTime)
            change_delivery_dates(orderCustomers,order,addTravelTime);

        #calculate new payment
        newPayment = calculate_truck_cost(truck,distanceTravel,totalToll,params['weightOccupied'],params['volumeOccupied'],True,numCustomers);
        truck.weightFilled += params['weightOccupied'];
        truck.volumeFilled += params['volumeOccupied'];
        truck.save();
        departure = params['departure'];
        delivery = calculate_ETA(travelTime,departure);
        departureDate = OrderDate(manufacturer=params['customer'],date=departure);
        deliveryDate = OrderDate(manufacturer=params['customer'],date=delivery);
        departureDate.save();
        deliveryDate.save();

        if truck.toPark == truck.owner:
            truck.toPark = destinationCity.transporters.first();
        else:
            truck.toPark = truck.owner;
        truck.save()

        #change order properties
        order.departure.add(departureDate);
        order.delivery.add(deliveryDate);
        order.destination = destinationCity;
        order.customers.add(customer);
        order.payment = newPayment;
        order.weightOccupied=truck.weightFilled;
        order.volumeOccupied=truck.volumerFilled;
        order.save()
        orderList.append(order);

    return orderList

def find_order_options(pickupDate,source,destination,goodsWeight,goodsVolume,manufacturer):
    manuParams = {
        'departure':pickupDate,
        'source':source,
        'destination':destination,
        'weightOccupied':goodsWeight,
        'volumeOccupied':goodsVolume,
        'customer':manufacturer,
    };

    manuState = manufacturer.location.state;
    cities = City.objects.filter(state=manuState);
    stateTans = [];
    for city in cities:
        transporters = Transporter.objects.filter(location=city);
        if len(transporters) != 0:
            stateTrans.extend(transporters);

    freeTruckList = [];
    shareTruckList = [];
    for transporter in stateTrans:
        for type in Truck.TYPES:
            freeTrucks = Truck.objects.filter(owner=transporter).filter(truckType=type).filter(booked=False);
            shareTrucks = Truck.objects.filter(owner=transporter).filter(truckType=type).filter(booked=False).filter(availability=True);
            if len(freeTrucks) != 0:
                for truck in freeTrucks:
                    if truck.weightCap >= goodsWeight and truck.volumeCap >= goodsVolume:
                        freeTruckList.append(truck);
                        break
                    else:
                        continue
            if len(bookedTrucks) != 0:
                for truck in shareTrucks:
                    truckOrder = Order.objects.get(truck=truck);
                    condition1 = truck.weightFilled >= goodsWeight;
                    condition2 = truck.volumeFilled >= goodsVolume;
                    condition3 = (pickupDate.day == truckOrder.departure.last().date.day and pickupDate.hour > truckOrder.departure.last().date.hour);
                    if condition1 and condition2 and condition3:
                        shareTruckList.append(truck);
                        break;
                    else:
                        continue;
    freeTruckOrders = create_free_orders(freeTruckList,manuParams);
    shareTruckOrders = create_share_orders(shareTruckList,manuParams);
    return shareTruckList.extend(freeTruckList);

def cost_efficient(order):
    return order.payment;

def time_efficient(order):
    customer = order.customers.last();
    deliveries = list(order.delivery.all());
    for delivery in deliveries:
        if delivery.manufacturer == customer:
            return delivery.date;

# Create your views here.
def options(request):
    if request.method == 'POST':
        pass
    else:
        return render(request, 'TruckShare/options.html')

def index(request):
    #user is redirected based on it's user profile
    if request.user.is_authenticated:
        if request.user.is_manufacturer:
            if request.method == 'POST':
                pickupDate = request.POST['pickupDate'];
                source = request.POST['source'];
                destination = request.POST['destination'];
                goodsWeight = request.POST['goodsWeight'];
                goodsVolume = request.POST['goodsVolume'];

                pickupDate = create_date_object(pickupDate);
                optionsList = find_order_options(pickupdate,source,destination,goodsWeight,goodsVolume,request.user.manufacturer);
                deliveryDates = find_delivery_dates(orderList);
                #Sort the optionsList according to time efficiency and cost efficiency;
                costOptions = optionsList.sort(key=order_efficient);
                timeOptions = optionsList.sort(key=time_efficient);

                ctx = {
                    'costOptions': costOptions,
                    'timeOptions': timeOptions,
                }

                return render(request,'TruckShare/options.html', ctx);

            else:
                cities = City.objects.exclude(name__startswith="State-Center");
                manuCity = request.user.manufacturer.location;
                context = {
                'cities': cities,
                'manuCity':manuCity,
                }
                return render(request, 'TruckShare/manuIndex.html', context);
        if request.user.is_transporter:
            return render(request, 'TruckShare/transIndex.html');
    #user can login or register
    else:
        return render(request, 'TruckShare/login.html');

def register(request):
    if request.method == 'POST':
        #print(request.POST)
        email = request.POST['email'];
        username = email.split('@')[0];

        password = request.POST['password'];
        confirmation = request.POST['confirmation'];

        if password != confirmation:
            return render(request, "TruckShare/register.html", {
                "message": "Passwords must match."
            })

        companyName = request.POST['companyName'];
        phoneNo = request.POST['phoneNo'];
        cityName = request.POST['location'];
        location = City.objects.get(name=cityName);
        userType = request.POST['user'];
        is_transporter,is_manufacturer = False,False;

        if userType == 'transporter':
            is_transporter = True;
            laborCost = int(request.POST['laborCost']);

        if userType == 'manufacturer':
            is_manufacturer = True;
            #one liner for converting goods types string with ',' in to list of goods.
            goodsTypes = [x for x in map(lambda string: string.strip(),request.POST['goodsTypes'].split(','))];
            goodsTypes = ''.join(goodsTypes);


        #try to create a user
        try:
            if is_manufacturer:
                user = User.objects.create_user(username,email,password,
                            is_manufacturer=is_manufacturer,
                            companyName=companyName,
                            phoneNo=phoneNo,
                            );
            if is_transporter:
                user = User.objects.create_user(username,email,password,
                            is_transporter=is_transporter,
                            companyName=companyName,
                            phoneNo=phoneNo,)
            user.save();
        except IntegrityError as e:
            print(e);
            return render(request, "TruckShare/register.html", {
                "message": "Email address already taken."
            });

        if is_transporter:
            transporter = Transporter(user=user,laborCost=laborCost,location=location);
            transporter.save();
            login(request,user);

            return HttpResponseRedirect(reverse('addTrucks', kwargs={'transporterId':transporter.id}))
            context = {
                'truckTypes':Truck().TYPES
            };
            return render(request, 'TruckShare/addtrucks.html', context);
        if is_manufacturer:
            manufacturer = Manufacturer(user=user,location=location,goodsTypes=goodsTypes);
            manufacturer.save()
            login(request, user);

            return HttpResponseRedirect(reverse('index'))

    else:
        cities = City.objects.exclude(name__startswith="State-Center");
        context = {
        'cities': cities,
        }
        return render(request, 'TruckShare/register.html', context);

def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        email = request.POST["email"]
        password = request.POST["password"]
        user = authenticate(request, username=email.split('@')[0], password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "TruckShare/login.html", {
                "message": "Invalid email and/or password."
            })
    else:
        return render(request, 'TruckShare/login.html');

def logout_view(request):
    logout(request);
    return HttpResponseRedirect(reverse('index'));


def add_trucks(request,transporterId):
    transporter = Transporter.objects.get(pk=transporterId);
    truckInfo = {
        'SMT1':{
            'weightCap':9000,
            'volumeCap':24000,
            'maxSpeed':50,
            'mileage':7.5
        },
        'SMT2':{
            'weightCap':9000,
            'volumeCap':24000,
            'maxSpeed':60,
            'mileage':7.0
        },
        'LMT1':{
            'weightCap':16000,
            'volumeCap':57000,
            'maxSpeed':35,
            'mileage':5.5
        },
        'LMT2':{
            'weightCap':9000,
            'volumeCap':24000,
            'maxSpeed':45,
            'mileage':5.0
        },
    };
    if request.method == "POST":
        truckType = request.POST['truckType'];
        numTrucksOwned = int(request.POST['trucksOwned']);
        cost1 = int(request.POST['cost1']);
        cost2 = int(request.POST['cost2']);
        weightCap = truckInfo[truckType]['weightCap'];
        volumeCap = truckInfo[truckType]['volumeCap'];
        maxSpeed = truckInfo[truckType]['maxSpeed'];
        mileage = truckInfo[truckType]['mileage'];
        owner = request.user.transporter
        parkedAt = request.user.transporter

        for i in range(numTrucksOwned):
            truck = Truck(truckType=truckType,
                          costFact1=cost1,
                          costFact2=cost2,
                          weightCap=weightCap,
                          volumeCap=volumeCap,
                          maxSpeed=maxSpeed,
                          mileage=mileage,
                          owner=owner,
                          parkedAt=parkedAt
                          );
            truck.save()
        prevOwned = transporter.numTrucksOwned;
        currentOwned = prevOwned + numTrucksOwned;
        transporter.numTrucksOwned = currentOwned;
        transporter.save()

        return HttpResponseRedirect(reverse('trucks'));
    else:
        context = {
            'truckTypes': Truck().TYPES
        };
        return render(request, 'TruckShare/addtrucks.html', context);


def trucks(request):
    if request.method == 'POST':
        truckType = request.POST['truckType'];
        costFact1 = request.POST['cost1'];
        costFact2 = request.POST['cost2'];

        trucks = Truck.objects.filter(owner=request.user.transporter).filter(truckType=truckType);
        for truck in trucks:
            truck.costFact1 = int(costFact1);
            truck.costFact2 = int(costFact2);
            truck.save()

        return HttpResponseRedirect(reverse('trucks'));

    else:
        otherTrucksParked = Truck.objects.filter(parkedAt=request.user.transporter).exclude(owner=request.user.transporter);
        ownerTrucks = dict()
        ownerTrucksParked = len(Truck.objects.filter(owner=request.user.transporter).filter(parkedAt=request.user.transporter));
        for type in Truck.TYPES:
            trucks = Truck.objects.filter(owner=request.user.transporter).filter(truckType=type[0]).filter(parkedAt=request.user.transporter);
            if len(trucks) != 0:
                ownerTrucks[type] = (trucks[0],len(trucks),type[1]);
            else:
                continue;

        context = {
            'otherTrucksParked': otherTrucksParked,
            'numOtherTrucks': len(otherTrucksParked),
            'ownerTrucks': ownerTrucks,
            'ownerTrucksParked':ownerTrucksParked,
        };

        return render(request, 'TruckShare/trucks.html', context)


def transporter_profile(request,transporterId):
    transporter = Transporter.objects.get(pk=transporterId);
    ownerTrucks = dict()
    for type in Truck.TYPES:
        trucks = Truck.objects.filter(owner=transporter).filter(truckType=type[0]);
        if len(trucks) != 0:
            ownerTrucks[type] = (trucks[0],len(trucks),type[1]);
        else:
            continue;

    context ={
        'ownerTrucks': ownerTrucks,
        'transporter': transporter
    };
    return render(request, 'TruckShare/transprofile.html', context)


def compare(request):
    cities = City.objects.filter(state=request.user.transporter.location.state);
    transporters = [];
    for city in cities:
        cityTrans = city.transporters.all();
        #never use is/is not to compare two model objects as they are both different instances!
        if city != request.user.transporter.location:
            if len(cityTrans) != 0:
                transporters.extend(cityTrans);
        else:
            for transporter in cityTrans:
                if transporter != request.user.transporter:
                    transporters.append(transporter);
                else: continue;

    ctx = {
        'transporters' : transporters,
    };
    return render(request, 'TruckShare/compare.html', ctx);
