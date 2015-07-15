# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User
from django.utils.encoding import python_2_unicode_compatible
from django.core.exceptions import ValidationError
from django.conf import settings
from ckeditor.fields import RichTextField

import os


def save_user_photo(instance, filename):
    storage_path = "/".join(instance.user.username, filename)
    print storage_path
    return storage_path


def save_media_file(instance, filename):
    storage_path = "/".join([instance.user.username, instance.file_type, filename])
    print storage_path
    return storage_path


# Сохранение фотографии работы
def save_work_photo(instance, filename):    
    storage_path = str(instance.organization.id)
    if instance.album:
        storage_path = storage_path + "/" + str(instance.album.id)
    storage_path = storage_path + "/" + filename
    return storage_path


def save_job_icon(instance, filename):
    storage_path = "icons/" + filename
    return storage_path


def save_organization_logo(instance, filename):
    storage_path = 'logos/' + filename
    return storage_path


class WorkCategory(models.Model):
    name = models.CharField(u"Наименование категории работ", max_length=100)
    icon = models.ImageField(upload_to="icons/", blank=True, default=None)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'Категория работ'
        verbose_name_plural = u'Категории работ'


class WorkType(models.Model):
    name = models.CharField(u"Вид работы", max_length=100)
    category = models.ForeignKey(WorkCategory, verbose_name=u"Категория работ")

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'Вид работы'
        verbose_name_plural = u'Виды работ'


class City(models.Model):
    name = models.CharField(u'Город', max_length=40)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'Город'
        verbose_name_plural = u'Города'


class WorkSpec(models.Model):

    WORK_SPEC = (
        (u'industrial', u'Промышленное строительство'),
        (u'individual', u'Частное строительство'),
        (u'all', u'Все')
    )

    class Meta:
        verbose_name = u"Специализация"
        verbose_name_plural = u"Специализации работ"

    def __unicode__(self):
        return self.get_name_display()

    name = models.CharField(u"Специализация", max_length=50, choices=WORK_SPEC)


class OrganizationProfile(models.Model):    

    class Meta:
        verbose_name = u'Организация'
        verbose_name_plural = u'Организации'

    name = models.CharField(u'Название организации', max_length=100)
    city = models.ForeignKey(City, verbose_name=u"Город регистрации", related_name="reg_city", null=True)
    address = models.CharField(u'Адрес', max_length=180, blank=True)
    job_types = models.ManyToManyField(WorkType, verbose_name=u"Виды выполняемых работ")
    logo = models.ImageField(u'Логотип организации', upload_to=save_organization_logo, blank=True, default=None)
    spec = models.ManyToManyField(WorkSpec, verbose_name=u"Специализация", default=u'Все')
    description = models.TextField(u"Обшая информация об организации", blank=True)
    landline_phone = models.CharField(u"Стационарный телефон", max_length=30, blank=True, default='')
    mobile_phone = models.CharField(u"Мобильный телефон", max_length=30, blank=True, default='')
    mobile_phone2 = models.CharField(u"Второй мобильный телефон", max_length=30, blank=True, default='')
    fax = models.CharField(u"Номер факса", max_length=40, blank=True, default='')
    web_site = models.URLField(u"Web-страница",  max_length=100, blank=True)
    email = models.EmailField(u"Контактный e-mail", max_length=100, blank=True)

    work_cities = models.ManyToManyField(City, verbose_name=u"Организация работает в городах")

    password = models.CharField(u'Пароль', max_length=120, blank=True, null=True, default=None)
    login = models.CharField(u'Логин на сайте', max_length=100, blank=True, null=True, default=None)

    collegues = models.ManyToManyField('self', verbose_name=u"Коллеги", related_name="collegues", blank=True)

    def save(self, *args, **kwargs):
        if not self.landline_phone and not self.mobile_phone and not self.mobile_phone2 and not self.fax:
            raise ValidationError(u"Заполните хотя бы одно из полей: " + ", ".join([
                OrganizationProfile._meta.get_field_by_name('landline_phone')[0].verbose_name,
                OrganizationProfile._meta.get_field_by_name('mobile_phone')[0].verbose_name,
                OrganizationProfile._meta.get_field_by_name('mobile_phone2')[0].verbose_name,
                OrganizationProfile._meta.get_field_by_name('fax')[0].verbose_name,
            ]))
        else:
            super(OrganizationProfile, self).save(*args, **kwargs)

    def clean(self):
        if not self.landline_phone and not self.mobile_phone and not self.mobile_phone2 and not self.fax:
            raise ValidationError(u"Заполните хотя бы одно из полей: " + ", ".join([
                OrganizationProfile._meta.get_field_by_name('landline_phone')[0].verbose_name,
                OrganizationProfile._meta.get_field_by_name('mobile_phone')[0].verbose_name,
                OrganizationProfile._meta.get_field_by_name('mobile_phone2')[0].verbose_name,
                OrganizationProfile._meta.get_field_by_name('fax')[0].verbose_name,
            ]))

    def __unicode__(self):
        return self.name

    def get_spec(self):
        return ', '.join([s.get_name_display() for s in self.spec.all()])
    get_spec.short_description = u'Специализация'


class UserProfile(models.Model):
    REG_TYPE_CHOICES = (
        ('client', u'Заказчик'),
        ('master', u'Исполнитель'),
        ('seller', u'Продавец'),
    )

    class Meta:
        verbose_name = u"Зарегистрированный пользователь"
        verbose_name_plural = u"Зарегистрированные пользователи"

    user = models.OneToOneField(User)
    reg_type = models.CharField(u"Вид регистрации", choices=REG_TYPE_CHOICES, default='client', max_length=20)
    phone = models.CharField(u"Контактный телефон", max_length=25, blank=True, default="")
    contact_name = models.CharField(u"Контактное имя", max_length=60, blank=True, default="")
    profile_image = models.ImageField(u"Логотип или фото", upload_to=save_user_photo, null=True)


class JobSuggestion(models.Model):
    class Meta:
        verbose_name = u"Предложение по работе"
        verbose_name_plural = u"Предложения по работе"
    short_header = models.CharField(u"Краткий заголовок заявки", max_length=50, default="",
                                    help_text=u"Краткий заголовок заявки")
    contact_name = models.CharField(u"Контактное лицо", max_length=100, default="")
    job_type = models.ForeignKey(WorkType, verbose_name=u"Вид работ", null=True, default="")
    description = models.TextField(u"Описание работы", default="")
    phone = models.CharField(u"Контактный телефон", max_length=25, default="")
    email = models.EmailField(u"Электронная почта", default="")
    date_created = models.DateTimeField(verbose_name=u"Дата создания", auto_now_add=True)
    job_spec = models.ForeignKey(WorkSpec, verbose_name=u"Специализация", null=True, default="")

    def __unicode__(self):
        return self.short_header    


class UserMedia(models.Model):
    FILE_TYPE_CHOICES = (
        ('video', u'Video'),
        ('image', u'Image'),
    )

    class Meta:
        verbose_name = u"Фото или видео работы мастера"
        verbose_name_plural = u"Фото и видео примеры работы мастера"

    work_file = models.FileField(upload_to=save_media_file)
    file_type = models.CharField(u"Тип записи работы", max_length=10, choices=FILE_TYPE_CHOICES, default="image")
    account = models.ForeignKey(UserProfile, verbose_name=u"Пользователь", null=True)


class WorkPhotoAlbum(models.Model):
    class Meta:
        verbose_name = u"Фотоальбом организации"
        verbose_name_plural = u"Фотоальбомы организации"

    organization = models.ForeignKey(OrganizationProfile, verbose_name=u"Организация", null=False)
    name = models.CharField(u"Название альбома", max_length=60)

    def save(self, *args, **kwargs):
        super(WorkPhotoAlbum, self).save(*args, **kwargs)
        album_folder = settings.MEDIA_ROOT + str(self.organization.id) + "//" + str(self.id)
        print album_folder      
        if not os.path.exists(album_folder):
            os.makedirs(album_folder)                
        
    def __unicode__(self):
        return self.name


class WorkPhoto(models.Model):
    class Meta:
        verbose_name = u"Фотография выполненной работы"
        verbose_name_plural = u"Фотографии выполненных работ"

    organization = models.ForeignKey(OrganizationProfile, verbose_name=u"Организация", null=True)
    album = models.ForeignKey(WorkPhotoAlbum, verbose_name=u"Альбом", null=True, blank=True)
    photo = models.ImageField(u'Фото сделанной работы', upload_to=save_work_photo)

    def __unicode__(self):
        return self.photo.url


class Article(models.Model):
    class Meta:
        verbose_name = u"Статья о стройке и ремонте"
        verbose_name_plural = u"Статьи о стройке и ремонте"

    name = models.CharField(u"Название статьи", max_length=100)
    content = RichTextField()
    job_spec = models.ForeignKey(WorkSpec, verbose_name=u"Специализация", null=True, default="")
    date_created = models.DateTimeField(u"Дата создания статьи", auto_now_add=True, null=True)
    date_modified = models.DateTimeField(u"Дата последнего изменения статьи", auto_now=True, null=True)


    def __unicode__(self):
        return self.name
