# views.py
from .decorators import agent_login_required,customer_login_required,login_required
from django.utils.decorators import method_decorator
from django.shortcuts import render, get_object_or_404, redirect
from .models import *
from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import UserRegistrationForm,AgentForm, CustomerForm, PaymentsForm,CustomerFormEdit,AgentEditForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password, check_password
from django.views.generic import ListView,  DetailView, TemplateView, DeleteView
from django.urls import reverse
from django.views.generic.edit import UpdateView
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.db.models import Sum
from django.urls import reverse_lazy

# Register views:
# 1. Admin register view
class RegisterUserView(View):
    def get(self, request):
        form = UserRegistrationForm()
        return render(request, 'registration/register.html', {'form': form})

    def post(self, request):
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Check if passwords match before saving
            password = form.cleaned_data['password']
            password_confirmation = form.cleaned_data['password_confirmation']
            if password != password_confirmation:
                # Handle password mismatch error (e.g., add to form errors)
                form.add_error('password_confirmation', 'Passwords do not match.')
            else:
                # Passwords match, save the user
                admin = Admin(username=form.cleaned_data['username'],
                              email=form.cleaned_data['email'],
                              password=password)
                admin.save()
                # You can add login logic here if needed
                return redirect('home')  # Redirect to the home page after registration
        return render(request, 'registration/register.html', {'form': form})

# 2. Customer register view
@login_required
def register_customer(request):
    form = CustomerForm()

    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            # Set success message
            messages.success(request, 'Customer registered successfully!')
            # Redirect to the same page after successful form submission
            return redirect('register_customer')

    context = {'form': form}
    return render(request, 'dashboard/admin/register_customer.html', context)

# 3. Agent register view
@login_required
def register_agent(request):
    form = AgentForm()

    if request.method == 'POST':
        form = AgentForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, 'Customer registered successfully!')
            # Redirect to the same page after successful form submission
            return redirect('register_agent')

    context = {'form': form}
    return render(request, 'dashboard/admin/register_agent.html', context)


# All Login views
# 1. Admin login view
def login_admin(request):
    error_message = ''  # Initialize error_message with an empty string

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            user = Admin.objects.get(username=username)
        except Admin.DoesNotExist:
            # Display a generic error message
            messages.error(request, 'Invalid username or password')
            return redirect('login_admin')  # Redirect back to the login page

        # Use check_password to compare hashed passwords
        if check_password(password, user.password):
            request.session['username'] = user.username
            # Passwords match, redirect to home
            return redirect('home')  # Assuming 'home' is a valid URL pattern
        else:
            # Set error_message for invalid password
            error_message = "Invalid username or password"
            return redirect('login_admin')

    # Pass error_message as context to the template
    return render(request, 'registration/login.html', {'error_message': error_message})

# 2. Agent login view
def login_agent(request):
    if request.method == 'POST':
        agent_id = request.POST.get('agent_id')

        try:
            user = Agent.objects.get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return HttpResponse('Agent does not exist')

        # If the agent is found, store agent_id in session
        if user is not None:
            request.session['agent_id'] = user.agent_id
            return redirect('payment_start')
        else:
            return HttpResponse('Invalid ID')

    return render(request, 'registration/agent_login.html')

# 3. client login/payment starting view
@agent_login_required
def payment_start(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')

        try:
            user = Customer.objects.get(customer_id=customer_id)
        except Customer.DoesNotExist:
            return HttpResponse('Customer does not exist')

        if user:
            request.session['customer_id'] = user.customer_id
            # User exists, redirect to agent with user details
            return redirect('payment', user_id=user.customer_id)
        else:
            return HttpResponse('Invalid id')

    return render(request, 'dashboard/agent/payment_form.html')



# Payment History view
# 1
def client_payment_history(request, user_id):
    user = get_object_or_404(Customer, customer_id=user_id)
    user_payments = Payments.objects.filter(customer__customer_id=user_id)
    return render(request, 'dashboard/agent/history.html', {'user': user, 'user_payments': user_payments})

def admin_payment_history(request, user_id):
    user = get_object_or_404(Customer, customer_id=user_id)
    user_payments = Payments.objects.filter(customer__customer_id=user_id)
    return render(request, 'dashboard/admin/payment_history.html', {'user': user,'user_payments': user_payments})

    

    
@customer_login_required
def payment(request, user_id):
    user = get_object_or_404(Customer, customer_id=user_id)
    success_message = None
    error_message = None

    # Retrieve agent_id and agent_name from session
    agent_id = None
    agent_name = None
    if 'agent_id' in request.session:
        agent_id = request.session['agent_id']
        try:
            agent = Agent.objects.get(agent_id=agent_id)
            agent_name = agent.username
        except Agent.DoesNotExist:
            pass  # Handle the case where agent_id does not correspond to any existing agent

    if request.method == 'POST':
        form = PaymentsForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.customer = user
            payment.received_by_id = agent_id  # Set the received_by field to agent_id

            # Additional validation
            if user.payment_category != 0 and payment.amount_paid % user.payment_category != 0:
                error_message = "Invalid amount entered, try again."
                return render(request, 'dashboard/agent/form.html', {'user': user, 'form': form, 'error_message': error_message, 'agent_name': agent_name})

            payment.save()
            success_message = 'Payment successful!'
            form = PaymentsForm()  # Reinitialize the form with an empty instance

            # Redirect to another page upon successful payment
            return redirect(reverse('payment_start'))  # Replace 'success_page' with the name of your success page URL pattern
        else:
            error_message = "Form is not valid"
    else:
        form = PaymentsForm()

    return render(request, 'dashboard/agent/form.html', {'user': user, 'form': form, 'success_message': success_message, 'error_message': error_message, 'agent_name': agent_name})

@method_decorator(login_required, name='dispatch')
class HomeView(TemplateView):
    template_name = 'dashboard/admin/index.html'
    
    def get_queryset(self):
        # You can customize the queryset here if needed
        return Customer.objects.all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate total amount paid
        total_amount_paid = Payments.objects.aggregate(total=Sum('amount_paid'))['total']
        if total_amount_paid is None:
            total_amount_paid = 0
        context['total_amount_paid'] = total_amount_paid
        
        # Other context data
        total_agents = Agent.objects.count()
        total_customer = Customer.objects.count()
        context['total_agents'] = total_agents
        context['total_customer'] = total_customer
        
        return context

@method_decorator(login_required, name='dispatch')
class Agentlist(ListView):
    model = Agent
    template_name = 'dashboard/admin/team.html'
    context_object_name = 'agent_list'  # Specify the context variable name for the queryset

    def get_queryset(self):
        # You can customize the queryset here if needed
        return Agent.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_agents = Agent.objects.count()
        total_customer = Customer.objects.count()
        context['total_agents'] = total_agents
        context['total_customer'] = total_customer
        return context

@method_decorator(login_required, name='dispatch')
class AgentEditView(UpdateView):
    model = Agent
    form_class = AgentEditForm
    template_name = 'dashboard/admin/agent_edit.html'
    success_url = reverse_lazy('agent_list')

    def form_valid(self, form):
        messages.success(self.request, 'Agent details updated successfully.')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')  
class CustomerList(ListView):
    model = Customer
    template_name = 'dashboard/admin/customer_list.html'
    context_object_name = 'customer_list'  # Specify the context variable name for the queryset

    def get_queryset(self):
        # You can customize the queryset here if needed
        return Customer.objects.all()
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_agents = Agent.objects.count()
        total_customer = Customer.objects.count()
        context['total_agents'] = total_agents
        context['total_customer'] = total_customer
        return context

class CustomerDelete(DeleteView):
    model = Customer
    success_url = reverse_lazy('customer-list') 

@method_decorator(login_required, name='dispatch')
class CustomerEditView(UpdateView):
    model = Customer
    form_class = CustomerFormEdit
    template_name = 'dashboard/admin/customer_edit.html'
    success_url = reverse_lazy('customer_list')

    def form_valid(self, form):
        messages.success(self.request, 'Customer details updated successfully.')
        return super().form_valid(form)

class CustomerDeleteView(DeleteView):
    model = Customer
    template_name = 'dashboard/admin/confirm_delete.html'
    success_url = reverse_lazy('customer_list')

def agent_logout(request):
    if 'agent_id' in request.session:
        session_key = request.session.session_key
        request.session.flush()  # Clear the session data
        Session.objects.filter(session_key=session_key).delete()  # Delete the session from the database
    return redirect('/')  # Redirect to the login page after logout

def customer_logout(request):
    if 'customer_id' in request.session:
        session_key = request.session.session_key
        request.session.flush()  # Clear the session data
        Session.objects.filter(session_key=session_key).delete()  # Delete the session from the database
    return redirect('login')  # Redirect to the login page after logout\

def admin_logout(request):
    if 'username' in request.session:
        session_key = request.session.session_key
        request.session.flush()  # Clear the session data
        Session.objects.filter(session_key=session_key).delete()  # Delete the session from the database
    return redirect('login_admin')  # Redirect to the login page after logout\
