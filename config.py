import os
from dotenv import load_dotenv

load_dotenv()

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Email Configuration
GMAIL_USER = 'no-reply@devsort.net'
GMAIL_PASSWORD = 'EF#D#i8@0#'

# Stripe Price IDs
STRIPE_PRICE_IDS = {
    'basic': {
        'weekly': os.getenv('STRIPE_PRICE_BASIC_WEEKLY'),
        'monthly': os.getenv('STRIPE_PRICE_BASIC_MONTHLY'),
        'yearly': os.getenv('STRIPE_PRICE_BASIC_YEARLY')
    },
    'standard': {
        'weekly': os.getenv('STRIPE_PRICE_STANDARD_WEEKLY'),
        'monthly': os.getenv('STRIPE_PRICE_STANDARD_MONTHLY'),
        'yearly': os.getenv('STRIPE_PRICE_STANDARD_YEARLY')
    },
    'professional': {
        'weekly': os.getenv('STRIPE_PRICE_PROFESSIONAL_WEEKLY'),
        'monthly': os.getenv('STRIPE_PRICE_PROFESSIONAL_MONTHLY'),
        'yearly': os.getenv('STRIPE_PRICE_PROFESSIONAL_YEARLY')
    }
}

# Subscription Plans Configuration
SUBSCRIPTION_PLANS = {
    'basic': {
        'weekly': {
            'price': 19.99,
            'images_per_day': 3,
            'video_minutes_per_day': 5,
            'description': 'For personal use, hobbies, etc.',
            'perks': [
                'No more ads',
                '10 images per day',
                '5 minutes of video generation per day',
                'Limited accelerated image processing',
                'High-resolution saving'
            ]
        },
        'monthly': {
            'price': 39.99,
            'images_per_day': 15,
            'video_minutes_per_day': 10,
            'description': 'For personal use, hobbies, etc.',
            'perks': [
                'No more ads',
                '25 images per day',
                '10 minutes of video generation per day',
                'Limited accelerated image processing',
                'High-resolution saving'
            ]
        },
        'yearly': {
            'price': 399.99,
            'images_per_day': 30,
            'video_minutes_per_day': 15,
            'description': 'For personal use, hobbies, etc.',
            'perks': [
                'No more ads',
                '30 images per day',
                '15 minutes of video generation per day',
                'Limited accelerated image processing',
                'High-resolution saving'
            ]
        }
    },
    'standard': {
        'weekly': {
            'price': 29.99,
            'images_per_day': 5,
            'video_minutes_per_day': 30,
            'description': 'For freelancers and small businesses.',
            'perks': [
                'No more ads',
                '50 images per day',
                '30 minutes of video generation per day',
                'Faster image processing',
                'Priority support',
                'Access to premium templates'
            ]
        },
        'monthly': {
            'price': 79.99,
            'images_per_day': 10,
            'video_minutes_per_day': 60,
            'description': 'For freelancers and small businesses.',
            'perks': [
                'No more ads',
                '100 images per day',
                '1 hour of video generation per day',
                'Faster image processing',
                'Priority support',
                'Access to premium templates'
            ]
        },
        'yearly': {
            'price': 799.99,
            'images_per_day': 50,
            'video_minutes_per_day': 120,
            'description': 'For freelancers and small businesses.',
            'perks': [
                'No more ads',
                '150 images per day',
                '2 hours of video generation per day',
                'Faster image processing',
                'Priority support',
                'Access to premium templates'
            ]
        }
    },
    'professional': {
        'weekly': {
            'price': 59.99,
            'images_per_day': -1,  # Unlimited
            'video_minutes_per_day': 180,
            'description': 'For Larger creators, Educators, Agencies, Freelancers etc',
            'perks': [
                'No more ads',
                'Unlimited images per day',
                '3 hours of video generation per day',
                'Ultra-fast processing',
                'Exclusive AI-generated assets',
                'Priority support',
                'Advanced editing tools'
            ]
        },
        'monthly': {
            'price': 149.99,
            'images_per_day': -1,  # Unlimited
            'video_minutes_per_day': 300,
            'description': 'For Larger creators, Educators, Agencies, Freelancers etc',
            'perks': [
                'No more ads',
                'Unlimited images per day',
                '5 hours of video generation per day',
                'Ultra-fast processing',
                'Exclusive AI-generated assets',
                'Priority support',
                'Advanced editing tools'
            ]
        },
        'yearly': {
            'price': 1499.99,
            'images_per_day': -1,  # Unlimited
            'video_minutes_per_day': 600,
            'description': 'For Larger creators, Educators, Agencies, Freelancers etc',
            'perks': [
                'No more ads',
                'Unlimited images per day',
                '10 hours of video generation per day',
                'Ultra-fast processing',
                'Exclusive AI-generated assets',
                'Priority support',
                'Advanced editing tools'
            ]
        }
    }
}
