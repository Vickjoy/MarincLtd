from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_login_redirect_url(self, request):
        """
        Always redirect to React frontend after successful social login
        """
        logger.debug("CustomSocialAccountAdapter.get_login_redirect_url called")
        
        # Get the next parameter that was stored
        next_url = request.session.get('socialaccount_next_url') or request.GET.get('next')
        
        if next_url and next_url.startswith('/'):
            # Convert Django path to React route
            frontend_url = f"http://localhost:5173{next_url}"
        else:
            # Default redirect
            frontend_url = "http://localhost:5173/"
        
        logger.debug(f"Redirecting to: {frontend_url}")
        return frontend_url
    
    def pre_social_login(self, request, sociallogin):
        """
        Store the next URL before social login starts
        """
        next_url = request.GET.get('next')
        if next_url:
            request.session['socialaccount_next_url'] = next_url
            logger.debug(f"Stored next URL in session: {next_url}")
    
    def get_connect_redirect_url(self, request, socialaccount):
        """
        Handle account connection redirects
        """
        return "http://localhost:5173/"

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """
        Redirect to React frontend after regular login
        """
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url and next_url.startswith('/'):
            return f"http://localhost:5173{next_url}"
        return "http://localhost:5173/"