# -*- encoding: utf-8 -*-

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core import serializers
from django.db.models import Q

from smtplib import SMTPAuthenticationError

from remont.rem_forms import RegisterForm, OrganizationProfileModelForm, SuggestJobForm, OrganizationEditForm, UploadPhotoForm
from remont.models import WorkType, WorkCategory, JobSuggestion, OrganizationProfile, City, WorkSpec, \
                          WorkPhotoAlbum, WorkPhoto, Message, Review, PartnerRequest, Article
from remont.utils import get_pending_partner_requests, get_top_orgs, get_org_rating, get_org_logo, format_message_time

from lastActivityDate.users_activity_service import get_last_visit

from django.conf import settings
from django.contrib.auth import authenticate, login, logout

from remont.mail_sending_service import send_confirm_registration

from django.forms.formsets import formset_factory

from  django.contrib.auth.hashers import check_password

from datetime import datetime, date, time

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

import locale
import logging

logger = logging.getLogger('remont.default_logger')

# Главная страница приложения
def index(request):
  # Получаем выбранную специализацию
  sel_spec = request.session.get("sel_spec")

  job_suggestions = JobSuggestion.objects.order_by("-date_created")[:5]
  cities = City.objects.all()
  categories = WorkCategory.objects.all()

  categories_data = []
  for cat in categories:
    cat_item = {"id": cat.id, "name": cat.name}
    jobs = WorkType.objects.filter(category=cat)
    cat_jobs = []
    for job in jobs:
      cat_jobs.append({"id": job.id, "name": job.name})
    cat_item["jobs"] = cat_jobs
    categories_data.append(cat_item)

  work_specs = []
  work_specs.append({"id": 0, "value": u"Специализация работ", "selected": "", "disabled": "disabled=disabled"})
  work_specs.append({"id": -1,  "value": u"Все", "selected": "", "disabled": ""})
  for spec in WorkSpec.objects.all():
    work_specs.append({"id": spec.id, "value": spec.get_name_display(), "selected": "", "disabled": ""})

  if sel_spec:
    for spec in work_specs:
      if spec["id"] == sel_spec:
        logger.info("Selected job specialization: {0}".format(sel_spec))
        spec["selected"] = "selected=selected"
        break
  else:
    work_specs[0]["selected"] = "selected=selected"
    request.session["sel_spec"] = work_specs[0]["id"]

  request.session["work_specs"] = work_specs

  suggest_job_form = SuggestJobForm()
  device_type = request.flavour
  response_data = {
      "jobSuggestions": job_suggestions,
      "cities": cities,
      "logged_in": False,
      "categories": categories_data,
      "suggest_job_form": suggest_job_form,
      "top_orgs": get_top_orgs(),
      "mainPage": True,
      "device_type": device_type
  }
  # Check if user is logged in.
  if request.user.is_authenticated():
    response_data["logged_in"] = True
    newMessages = Message.objects.filter(was_read__isnull=True, msg_to=request.user)
    response_data["newMesagesAmount"] = len(newMessages)
    response_data["partner_requests"] = get_pending_partner_requests(request.user)

  # Получаем 5 самых новых статей.
  newest_articles = Article.objects.order_by("-date_created")[:5]
  response_data["newest_articles"] = newest_articles

  logger.info("Client's device type: {0}".format(request.flavour))

  if device_type == "full":
    return render(request, "remont/index.html", response_data)
  else:
    return render(request, "remont/mobile/index.html", response_data)


# Регистрация пользователя
def register(request):
  reg_form = RegisterForm()
  return render(request, "remont/register.html", {"reg_form": reg_form})


# Сохранение предложения о работе
def suggest_job_save(request):
  contact_person = unicode(request.REQUEST["contactPerson"])
  work_type = request.REQUEST["workType"]
  description = unicode(request.REQUEST["description"])
  phone = request.REQUEST["phone"]
  mail = request.REQUEST["mail"]
  header = request.REQUEST["shortHeader"]

  job_type = WorkType.objects.get(pk=int(work_type))
  job = JobSuggestion(contact_name=contact_person, job_type=job_type, description=description,
    phone=phone, email=mail, short_header=header)
  job.save()
  return redirect("/remont")

# Получаем список организаций(Для страницы)
def orgs_list(request):
  # Filter by organization specialization...
  sel_spec = request.session.get("sel_spec")
  org_spec = WorkSpec.objects.filter(id=int(sel_spec)).first()
  logged_org = ""

  if request.user.is_authenticated():
    logged_org = OrganizationProfile.objects.filter(account=request.user).first()

  orgs = OrganizationProfile.objects.all().order_by('name')
  if logged_org:
    orgs = orgs.exclude(id=logged_org.id)
  if org_spec:
    orgs = orgs.filter(spec=org_spec)

  nameStarts = request.GET.get("nameStarts", "")
  if nameStarts:
    logger.info("Filtering orgs list by name...")
    orgs = orgs.filter(name__icontains=nameStarts)

  orgs_list = []
  for org in orgs:
    org_data = {"id": org.id, "name": org.name, "rating": get_org_rating(org), "logo": get_org_logo(org)}
    orgs_list.append(org_data)

  logger.info("Amount of organizations: {0}".format(len(orgs_list)))
  return render(request, 'remont/orgs_list.html', {"orgs_list": orgs_list, "nameStarts": nameStarts})


# Поиск организации по ключевым словам, фильтр - промышленное, частное строительство, все.
def search_organizations(request):
  sel_spec = request.session.get("sel_spec")
  org_spec = WorkSpec.objects.filter(id=int(sel_spec)).first()
  logged_org = ""

  if request.user.is_authenticated():
    logged_org = OrganizationProfile.objects.filter(account=request.user).first()
  key_phrase = request.REQUEST["keyWords"]
  response_data = []

  # 1) Поиск по имени организации
  if org_spec:
    orgs_by_name = OrganizationProfile.objects.filter(name__istartswith=key_phrase, spec=org_spec)
  else:
    orgs_by_name = OrganizationProfile.objects.filter(name__istartswith=key_phrase)

  for org in orgs_by_name:
    if logged_org and logged_org.id != org.id:
      response_data.append({"id": org.id, "name": org.name, "logo": get_org_logo(org)})
    else:
      response_data.append({"id": org.id, "name": org.name, "logo": get_org_logo(org)})

  # 2) Поиск по ключевым словам из описания организации
  orgs_qset = OrganizationProfile.objects.filter(description__icontains=key_phrase)
  for org in orgs_qset:
    if logged_org and logged_org.id != org.id:
      response_data.append({"id": org.id, "name": org.name, "logo": get_org_logo(org)})
    else:
      response_data.append({"id": org.id, "name": org.name, "logo": get_org_logo(org)})

  logger.info("Found {0} organizations: ".format(len(response_data)))
  response = JsonResponse(response_data, safe=False)
  return response


@csrf_exempt
# Создание предложения по работе.
def suggest_job_save_ajax(request):
  job_type_id = request.POST.get("job_type", False)
  if job_type_id:
    job_type = WorkType.objects.filter(id=job_type_id).first()
  else:
    job_type = None

  job = JobSuggestion(
    contact_name=request.POST.get("contact_name", ""),
    job_type=job_type,
    description=request.POST.get("job_description", ""),
    phone=request.POST.get("contact_phone", ""),
    email=request.POST.get("contact_mail", ""),
    short_header=request.POST.get("job_header", "")
  )
  job_spec = request.session.get("sel_spec")
  logger.info("Work specialization: {0}".format(job_spec))
  work_spec = WorkSpec.objects.get(id=int(job_spec))
  job.job_spec = work_spec
  job.save()

  if job_type:
    type_name = job_type.name
  else:
    type_name = u''

  response_data = {'header': job.short_header, 'type_name': type_name,
      'date_created': job.date_created, 'description': job.description}
  response = JsonResponse(response_data, safe=False)
  return response


# Создает новую организацию на основе заполненной пользователем формы.
@csrf_exempt
def create_organization(request):
  if request.method == "POST":
    reg_form = RegisterForm(request.POST, request.FILES)
    if reg_form.is_valid():
      org = OrganizationProfile()
      org.name = reg_form.cleaned_data["name"]
      org.logo = reg_form.cleaned_data["logo"]
      # city_id = int(reg_form.cleaned_data["city"])
      # org.city = City.objects.filter(id=city_id).first()
      org.city = reg_form.cleaned_data["city"]
      org.address = reg_form.cleaned_data["address"]
      org.description = reg_form.cleaned_data["description"]
      org.landline_phone = reg_form.cleaned_data["landing_phone"]
      org.mobile_phone = reg_form.cleaned_data["mobile_phone"]
      org.mobile_phone2 = reg_form.cleaned_data["mobile_phone2"]
      org.fax = reg_form.cleaned_data["fax"]
      org.web_site = reg_form.cleaned_data["web_site"]
      org.email = reg_form.cleaned_data["email"]

      org.login = reg_form.cleaned_data["login"]
      password = reg_form.cleaned_data["password"]
      password_repeat = reg_form.cleaned_data["password_repeat"]
      org.password = password

      org.save()

      # Save Work in cities.
      work_cities = reg_form.cleaned_data["work_cities"]
      for c in work_cities:
        org.work_cities.add(c)

      # Save job types
      job_types = reg_form.cleaned_data["job_types"]
      for jt in job_types:
        org.job_types.add(jt)

      try:
        send_confirm_registration(org.email, org.account.id)
      except SMTPAuthenticationError as e:
        logger.error("Unable to send registration confirmation mail! Account activation should be done manually by site admin.")
      return render(request, 'remont/confirm_registration.html', {})
    else:
      return render(request, "remont/register.html", {"reg_form": reg_form})


# Вход на сайт
@csrf_exempt
def site_login(request):
  response_data = {}
  uname = request.POST["login"]
  passwd = request.POST["password"]
  user = authenticate(username=uname, password=passwd)

  response_data = {}

  if user is None:
    # Попытка авторизации, используя имя организации
    logger.error("Authorization error!")
    org = OrganizationProfile.objects.filter(name=uname).first()
    if org:
      uname = org.account.username
      user = authenticate(username=uname, password=passwd)

      if user is not None:
        if user.is_active:
          login(request, user)
          response_data["status"] = "success"
        else:
          response_data["status"] = "error"
          response_data["error_message"] = u"Аккаунт пользователя {0} не активирован!".format(uname)
          logger.error(response_data["error_message"])
    else:
      response_data["status"] = "error"
      response_data["error_message"] = "Неправильное имя пользователя или пароль"
      logger.error(response_data["error_message"])
  else:
    login(request, user)
    response_data["status"] = "success"

  response = JsonResponse(response_data, safe=False)
  return response


# Выход с сайта
@csrf_exempt
def site_logout(request):
  logout(request)
  return redirect("/remont")


# Получаем фотографии из альбома.
def get_album_photos(request):
  album_photos = []
  album_id = request.GET["album_id"]
  photo_album = WorkPhotoAlbum.objects.filter(id=album_id).first()
  if photo_album:
    photos = WorkPhoto.objects.filter(album=photo_album)
    for photo_obj in photos:
      album_photos.append({'id': photo_obj.id, 'url': photo_obj.photo.url})

  response = JsonResponse(album_photos, safe=False)
  return response


# Открывает страницу просмотра профайла организации
def view_profile(request):
  return render(request, "remont/view_profile.html", {"org_id": request.GET["org_id"]})


# Получаем информацию об организации в формате JSON
def get_profile_info(request):
  org_id = request.GET["org_id"]
  org_profile = OrganizationProfile.objects.filter(id=org_id).first()
  profile_json = {"id": org_profile.id, "name": org_profile.name, "city": org_profile.city.name,
    "address": org_profile.address, "rating": 3.5}

  profile_json["logo_url"] = get_org_logo(org_profile)

  collegs = org_profile.collegues.all()
  collegs_array = []
  for c in collegs:
    colleg_item = {"id": c.id, "name": c.name}
    colleg_item["logo_url"] = get_org_logo(c)
    collegs_array.append(colleg_item)

  profile_json["collegues"] = collegs_array

  job_types = [job.name for job in org_profile.job_types.all()]
  profile_json["job_types"] = job_types

  contacts = []
  if org_profile.landline_phone:
    contacts.append(org_profile.landline_phone)
  if org_profile.mobile_phone:
    contacts.append(org_profile.mobile_phone)
  if org_profile.mobile_phone2:
    contacts.append(org_profile.mobile_phone2)
  if org_profile.fax:
    contacts.append(org_profile.fax)
  if org_profile.web_site:
    contacts.append(org_profile.web_site)
  if org_profile.email:
    contacts.append(org_profile.email)

  profile_json["contacts"] = contacts
  profile_json["address"] = org_profile.address
  profile_json["about"] = org_profile.description

  photos = WorkPhoto.objects.filter(organization=org_profile)
  profile_json["photos"] = [p.photo.url for p in photos]

  if org_profile.account:
    logger.info("Organization user: {0}".format(org_profile.account.id))
    profile_json["last_visit"] = get_last_visit(org_profile.account.id)
  else:
    profile_json["last_visit"] = u"Никогда"

  reviews = Review.objects.filter(org=org_profile)
  profile_json["reviews_amount"] = len(reviews)

  response = JsonResponse(profile_json, safe=False)
  return response


# Отправляем сообщение организации(Другому пользователю)
@csrf_exempt
def send_text_mesaage(request):
  response_data = {}
  sender = None
  receiver_id = request.POST["org_id"]
  receiver_org = OrganizationProfile.objects.filter(id=receiver_id).first()
  if receiver_org.account:
    message_text = request.POST["message"]
    if request.user.is_authenticated():
      logger.info('User is authenticated!')
      sender = request.user
      msg = Message(msg_to=receiver_org.account, msg_from=sender, text=message_text)
      msg.save()
      logger.info("Message was successfully send")
      response_data["status"] = "success"
    else:
      response_data["status"] = "error"
      response_data["error_message"] = u"Организация {0} еще не активизировала свой аккаунт на сайте".format(receiver_org.name)
      logger.error(response_data["error_message"])

  return JsonResponse(response_data, safe=False)


# Подтверждение пользователем своей регистрации
def confirm_registration(request):
  user_id = request.GET["user_id"]
  if user_id:
    account = User.objects.filter(id=user_id).first()
    account.is_active = True
    account.save()
    logger.info("Account was activated successfully!")

    return redirect("/remont")


# Редактируем профайл организации
@csrf_exempt
def edit_organization(request, id=None):
  if id:
    logger.info("User identifier: {0}".format(id))
    user = get_object_or_404(User, pk=id)
    org = get_object_or_404(OrganizationProfile, account=user)

    if request.POST:
      logger.info("Saving changes...")
      profile_form = OrganizationEditForm(request.POST, request.FILES, instance=org)
      if profile_form.is_valid():
        profile_form.save()
        logger.info("Organization changes were saved successfully!")
        redirect_url = '/remont/edit_organization/' + str(id)
        return redirect(redirect_url)
    else:
      profile_form = OrganizationEditForm(instance=org)
      photo_albums = WorkPhotoAlbum.objects.filter(organization=org)
      grouped_photos = []
      photos_amount = 0
      for ph_album in photo_albums:
        photos = WorkPhoto.objects.filter(album=ph_album)
        photos_amount += len(photos)
        album_info = {"id": ph_album.id, "name": ph_album.name, "photos": photos}
        grouped_photos.append(album_info)
        ungrouped_photos = WorkPhoto.objects.filter(organization=org, album__isnull=True)
        photos_amount += len(ungrouped_photos)
        if len(ungrouped_photos) > 0:
          unnamed_album = {"id": 0, "name": u"Другие фотографии", "photos": ungrouped_photos}
          grouped_photos.append(unnamed_album)

      return render(request, "remont/edit_profile.html", {
        "profile_form": profile_form,
        "work_photos": grouped_photos,
        "photos_amount": photos_amount
      })

  else:
    logger.error("No user id is defined!")


# Загрузка фотографий выполненных работ
@csrf_exempt
def upload_work_photos(request):
  org = OrganizationProfile.objects.filter(account = request.user).first()
  if request.method == "POST":
    files_to_upload = request.FILES.getlist("uploadPhoto")
    album_id = request.POST.get("albumId", False)
    if album_id:
      for f in files_to_upload:
        photo_obj = WorkPhoto(organization=org, photo=f, album=WorkPhotoAlbum.objects.filter(id=int(album_id)).first())
        photo_obj.save()
      return redirect("/remont/edit_album?album_id=" + album_id)
    else:
      for f in files_to_upload:
        photo_obj = WorkPhoto(organization=org, photo=f)
        photo_obj.save()
      return redirect("/remont/edit_organization/" + str(request.user.id))


# Создание нового фотоальбома
@csrf_exempt
def create_photo_album(request):
  org = OrganizationProfile.objects.filter(account = request.user).first()
  album = WorkPhotoAlbum(organization=org, name=request.POST["albumName"])
  album.save()
  response_data = {"id": album.id, "name": album.name, "photos": []}
  return JsonResponse(response_data, safe=False)


# Редактирование фотоальбома организации
def edit_album(request):
  album_id = request.GET["album_id"]
  album = WorkPhotoAlbum.objects.filter(id=int(album_id)).first()
  photos = WorkPhoto.objects.filter(album=album)
  return render(request, "remont/edit_album.html", {"album": album, "photos": photos})


# Удаление фотографии
@csrf_exempt
def delete_photo(request):
  photo_id = request.POST["photo_id"]
  WorkPhoto.objects.filter(id=int(photo_id)).delete()
  return JsonResponse({"photoId": photo_id}, safe=False)


# Изменение пароля акканта организации
@csrf_exempt
def change_password(request):
  if request.method == "POST":
    response_data = {}
    old_pass = request.POST["old_password"]
    new_pass = request.POST["new_password"]

    if request.user.is_authenticated():
      if check_password(old_pass, request.user.password):
        request.user.set_password(new_pass)
        request.user.save()
        response_data["status"] = "success"
      else:
        response_data["status"] = "failure"
        response_data["error"] = "Неправильный текущий пароль"

      return JsonResponse(response_data, safe=False)
    else:
      res = HttpResponse("Unautorized")
      res.status_code = 401
      return res


# Каталог работ
def jobs_list(request):
  work_types = WorkType.objects.order_by("category")
  types_data = {}
  for wt in work_types:
    if wt.category in types_data:
      types_data[wt.category].append(wt)
    else:
      types_data[wt.category] = [wt]

  return render(request, "remont/jobs_list.html", {"job_types": types_data})


# Получаем список организаций, выполняющий определенный вид работ
def get_orgs_by_job_type(request):
  job_type_id = request.GET["jobId"]
  job_type = WorkType.objects.filter(id=job_type_id).first()
  orgs = OrganizationProfile.objects.filter(job_types__id__exact=job_type_id)

  orgs_list = []
  for org in orgs:
    org_data = {"id": org.id, "name": org.name, "rating": get_org_rating(org), "logo": get_org_logo(org)}
    orgs_list.append(org_data)

  return render(request, "remont/job_orgs_list.html", {"orgs_list": orgs_list, "job_type": job_type})


# Создание запроса на добавление в партнеры
@csrf_exempt
def add_partner_request(request):
  if request.user.is_authenticated():
    sender = OrganizationProfile.objects.filter(account=request.user).first()
    recipient_id = request.POST["recipientId"]
    recipient = OrganizationProfile.objects.filter(id=recipient_id).first()
    logger.info("Sending partner request to organization with id {0}".format(recipient.id))
    partner_request = PartnerRequest(org_from=sender, org_to=recipient)
    partner_request.save()
    return JsonResponse({"status": "succcss"}, safe=False)
  else:
    res = HttpResponse("Unautorized")
    res.status_code = 401
    return res


# Подтверждение партнерства
@csrf_exempt
def approve_partner(request):
  if request.user.is_authenticated():
    sender_id = request.POST["senderId"]
    sender = OrganizationProfile.objects.filter(id=int(sender_id)).first()
    recipient = OrganizationProfile.objects.filter(account=request.user).first()

    partner_request = PartnerRequest.objects.filter(org_from=sender, org_to=recipient).first()
    partner_request.approved = True
    partner_request.save()

    recipient.collegues.add(sender)
    recipient.save()
    return JsonResponse({"status": "succcss"}, safe=False)
  else:
    res = HttpResponse("Unautorized")
    res.status_code = 401
    return res


# Отказ от партнерства
@csrf_exempt
def reject_partner(request):
  if request.user.is_authenticated():
    sender_id = request.POST["senderId"]
    sender = OrganizationProfile.objects.filter(id=sender_id).first()
    recipient = OrganizationProfile.objects.filter(account=request.user).first()

    partner_request = PartnerRequest.objects.filter(org_from=sender, org_to=recipient).delete()
    return JsonResponse({"status": "succcss"}, safe=False)
  else:
    res = HttpResponse("Unautorized")
    res.status_code = 401
    return res


# Меняем фильтр специализации работ
@csrf_exempt
def change_spec_filter(request):
  new_spec = request.POST["spec"]
  request.session["sel_spec"] = int(new_spec)
  return JsonResponse({"status": "success"})


# Получаем новые сообщения для пользователя.
def get_new_messages_for_user(request):
  new_messages = Message.objects.filter(was_read__isnull=True, msg_to=request.user).order_by("-was_written")
  new_messages_result = {}
  cur_datetime = datetime.now()
  cur_date = cur_datetime.strftime("%d-%m-%Y")
  cur_time = cur_datetime.strftime("%H:%M")

  for msg in new_messages:
    sender = msg.msg_from
    sender_id = str(sender.id)
    if not sender_id in new_messages_result:
      sender_name = sender.username
      sender_org = OrganizationProfile.objects.filter(account=sender).first()
      if sender_org:
        sender_logo = get_org_logo(sender_org)
      else:
        sender_logo = "/static/remont/images/info_empty.jpg"
      was_written_date = msg.was_written.strftime("%d-%m-%Y")
      was_written_time = msg.was_written.strftime("%H:%M")
      if was_written_date == cur_date:
        was_written = was_written_time
      else:
        was_written = was_written_date

      msg_item = {
          "msg_id": msg.id,
          "from_name": sender_name,
          "from_logo": sender_logo,
          "msg_text": msg.text,
          "msg_written": was_written,
          "messages_count": 1
      }
      new_messages_result[sender_id] = msg_item
    else:
      new_messages_result[sender_id]["messages_count"] = new_messages_result[sender_id]["messages_count"] + 1

  new_messages_array = []
  for key, data in new_messages_result.iteritems():
    new_messages_array.append({
      "msg_id": data["msg_id"],
      "sender_id": key,
      "from_name": data["from_name"],
      "from_logo": data["from_logo"],
      "msg_text": data["msg_text"],
      "msg_written": data["msg_written"],
      "messages_count": data["messages_count"]
    })

  return JsonResponse(new_messages_array, safe=False)


# Обработка ответа на сообщение от пользователя или организации
@csrf_exempt
def answer_mesaage(request):
  answer_response = {}
  message = request.POST.get("message", False)
  receiver_id = int(request.POST.get("receiver_id"), False)
  receiver = User.objects.filter(id=receiver_id).first()
  sender = request.user
  msg = Message(msg_to=receiver, msg_from=sender, text=message)
  msg.save()

  sender_org = OrganizationProfile.objects.filter(account=sender).first()

  answer_response = {
    "sender_id": msg.msg_from.id,
    "sender_name": msg.msg_from.username,
    "receiver_id": msg.msg_to.id,
    "receiver_name": msg.msg_to.username,
    "msg_text": msg.text,
    "was_written": format_message_time(msg.was_written),
    "sender_logo": get_org_logo(sender_org)
  }

  return JsonResponse(answer_response, safe=False)


# Получаение истории диалога с определенным пользователем.
@csrf_exempt
def get_dialogs_history(request):
  partner_id = request.GET.get("dialog_partner", False)
  dialog_partner = User.objects.filter(id=int(partner_id)).first()
  logged_user = request.user
  dialog_messages = Message.objects.filter(
      Q(msg_to=request.user, msg_from=dialog_partner) |
      Q(msg_from=request.user, msg_to=dialog_partner)).order_by("-was_written")

  messages_array = []
  for msg in dialog_messages:

    if msg.msg_to.id == request.user.id:
      msg.was_read = datetime.now()
      logger.info("Message was read!");
      msg.save()

    sender_org = OrganizationProfile.objects.filter(account=msg.msg_from).first()
    messages_array.append({
      "sender_id": msg.msg_from.id,
      "sender_name": msg.msg_from.username,
      "receiver_id": msg.msg_to.id,
      "receiver_name": msg.msg_to.username,
      "msg_text": msg.text,
      "was_written": format_message_time(msg.was_written),
      "sender_logo": get_org_logo(sender_org)
    })

  return JsonResponse(messages_array, safe=False)


# Проверяем, выбрана ли специализация работ(Для функционирования меню и поиска организаций).
@csrf_exempt
def check_spec(request):
  sel_spec = request.session.get("sel_spec")
  response_data = {}
  if sel_spec:
    response_data["spec_selected"] = "true"
  else:
    response_data["spec_selected"] = "false"
  return JsonResponse(response_data, safe=False)


# Получаем список статей, по 10 на 1 страницу.
@csrf_exempt
def articles_list(request):
  articles_list = Article.objects.order_by("-date_created")
  paginator = Paginator(articles_list, 10)
  logger.info("Pages amount: {0}".format(paginator.num_pages))

  active_page = request.GET.get("active_page")
  try:
    articles = paginator.page(active_page)
  except PageNotAnInteger:
    articles = paginator.page(1)
  except EmptyPage:
    articles = paginator.page(paginator.num_pages)

  return render(request, "remont/articles_list.html", {"articles": articles})


@csrf_exempt
def read_article(request, id=None):
  if(id):
    logger.info("Openning article with id: {0}".format(id))
    article = Article.objects.filter(pk=id).first()
    return render(request, "remont/read_article.html", {"article": article})
  else:
    logger.warning("No article selected!")
