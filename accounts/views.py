from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.contrib import messages


def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('device:device_list')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')

            # Redirect to next page or default to device list
            next_url = request.GET.get('next', 'device:device_list')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Handle user logout"""
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'You have been logged out successfully.')
        return redirect('accounts:login')

    return render(request, 'accounts/logout_confirm.html')
