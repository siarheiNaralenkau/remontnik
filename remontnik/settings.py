# -*- coding: utf-8 -*-

"""
Django settings for remontnik project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import sys
import codecs
import locale
import socket

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '-b1o=+9@9#*zs$iq@b4%c^r1e#845!gcz_#@b4^*c#vyo8-fx7'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

TEMPLATE_DIRS = [os.path.join(BASE_DIR, 'templates')]

ALLOWED_HOSTS = []

platform = sys.platform

if sys.platform.startswith("win"):
  MEDIA_ROOT = "c://MyDevelopment//MediaStorage//"
elif sys.platform.startswith("linux"):
  MEDIA_ROOT = "/home/media/remontnik/"
else:
  MEDIA_ROOT = "/home/media/"

MEDIA_URL = "media/"

# Environment configuration(local or remote)
ENVIRONMENT = os.environ.get('REM_ENVIRONMENT', 'local')

ADMIN_MEDIA_PREFIX = '/static/admin/'
# Application definition

INSTALLED_APPS = (
  'django.contrib.admin',
  'django.contrib.auth',
  'django.contrib.contenttypes',
  'django.contrib.sessions',
  'django.contrib.messages',
  'django.contrib.staticfiles',
  'django.db.backends.mysql',
  'ckeditor',
  'remont',
  'lastActivityDate',
)

MIDDLEWARE_CLASSES = (
  'django.contrib.sessions.middleware.SessionMiddleware',
  'django.middleware.common.CommonMiddleware',
  'django.middleware.csrf.CsrfViewMiddleware',
  'django.contrib.auth.middleware.AuthenticationMiddleware',
  'django.contrib.messages.middleware.MessageMiddleware',
  'django.middleware.clickjacking.XFrameOptionsMiddleware',
  'django.middleware.locale.LocaleMiddleware',
  'lastActivityDate.middleware.LastActivityMiddleware'
)

ROOT_URLCONF = 'remontnik.urls'

WSGI_APPLICATION = 'remontnik.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases
DATABASES = {
  'default': {
    'NAME': 'remontnik',
    'ENGINE': 'django.db.backends.mysql',
    'USER': 'remontnik',
    'PASSWORD': 'remontnik',
  }
}

if ENVIRONMENT == 'remote':
  DATABASES['default']['HOST'] = '31.130.201.148'
  DATABASES['default']['USER'] = 'remontnik'
  DATABASES['default']['PASSWORD'] = 'remontnik'

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

USE_TZ = False

TIME_ZONE = 'Europe/Minsk'

USE_I18N = True

USE_L10N = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'

# CKEditor settings
CKEDITOR_UPLOAD_PATH = "ckeditor_uploads/"
CKEDITOR_IMAGE_BACKEND = "pillow"
CKEDITOR_JQUERY_URL = STATIC_URL + "remont/js/jquery-2.1.3.min.js"
CKEDITOR_CONFIGS = {
  'default': {
    'toolbar': 'full',
    'height': 600,
    'width': 800,
    'language': 'ru'
  },
}

try:
  HOST_NAME = socket.gethostbyname(socket.gethostname())
except:
  HOST_NAME = "localhost"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
MAIL_FROM = "staatix.gomel@gmail.com"
MAIL_PASSWORD = "staatix2015"