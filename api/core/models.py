from __future__ import annotations

import functools
import logging
import typing
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Manager
from django.http import HttpRequest
from django.utils import timezone
from simple_history import register
from simple_history.models import HistoricalRecords as BaseHistoricalRecords
from simple_history.models import (
    ModelDelta,
    post_create_historical_m2m_records,
    post_create_historical_record,
    pre_create_historical_m2m_records,
    pre_create_historical_record,
)
from softdelete.models import SoftDeleteManager, SoftDeleteObject

from audit.constants import CREATED_MESSAGE, DELETED_MESSAGE, UPDATED_MESSAGE
from audit.related_object_type import RelatedObjectType

if typing.TYPE_CHECKING:
    from environments.models import Environment
    from organisations.models import Organisation
    from projects.models import Project
    from users.models import FFAdminUser


logger = logging.getLogger(__name__)


class UUIDNaturalKeyManagerMixin:
    def get_by_natural_key(self, uuid_: str):
        logger.debug("Getting model %s by natural key", self.model.__name__)
        return self.get(uuid=uuid_)


class AbstractBaseExportableModelManager(UUIDNaturalKeyManagerMixin, Manager):
    pass


class AbstractBaseExportableModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    objects = AbstractBaseExportableModelManager()

    class Meta:
        abstract = True

    def natural_key(self):
        return (str(self.uuid),)


class SoftDeleteExportableManager(UUIDNaturalKeyManagerMixin, SoftDeleteManager):
    pass


class SoftDeleteExportableModel(SoftDeleteObject, AbstractBaseExportableModel):
    objects = SoftDeleteExportableManager()

    class Meta:
        abstract = True


class BaseHistoricalModel(models.Model):
    include_in_audit = True

    master_api_key = models.ForeignKey(
        "api_keys.MasterAPIKey", blank=True, null=True, on_delete=models.DO_NOTHING
    )

    class Meta:
        abstract = True


class _AbstractBaseAuditableModel(models.Model):
    """
    A base Model class that all models we want to be included in the audit log should inherit from.

    Some field descriptions:

     :related_object_type: a RelatedObjectType enum representing the related object type of the model.
        Note that this can be overridden by the `get_related_object_type` method in cases where it's
        different for certain scenarios.
    """

    related_object_type: RelatedObjectType

    class Meta:
        abstract = True

    def get_skip_create_audit_log(self) -> bool:
        """Override if audit log records should NOT be written when model is created/updated/deleted"""
        return False

    def get_create_log_message(self, history_instance) -> str | None:
        """Override if audit log records should be written when model is created"""
        return None

    def get_update_log_message(self, history_instance, delta: ModelDelta) -> str | None:
        """Override if audit log records should be written when model is updated"""
        return None

    def get_delete_log_message(self, history_instance) -> str | None:
        """Override if audit log records should be written when model is deleted"""
        return None

    def get_organisations_project_environment(
        self,
    ) -> tuple[typing.Iterable[Organisation], Project | None, Environment | None]:
        environment = self._get_environment()
        project = self._get_project() or (environment.project if environment else None)
        organisations = [project.organisation] if project else self._get_organisations()
        if organisations is None:
            raise RuntimeError(
                f"{self.__class__.__name__}: One of _get_organisations(), _get_project() or _get_environment() must "
                "be implemented and return a non-null value"
            )
        return organisations, project, environment

    def get_extra_audit_log_kwargs(self, history_instance) -> dict:
        """Add extra kwargs to the creation of the AuditLog record"""
        return {}

    def get_audit_log_author(self, history_instance) -> FFAdminUser | None:
        """Override the AuditLog author (in cases where history_user isn't populated for example)"""
        return None

    def get_audit_log_related_object_id(self, history_instance) -> int | None:
        """Override the related object ID in cases where it shouldn't be self.id"""
        return self.pk

    def get_audit_log_related_object_type(
        self, history_instance
    ) -> RelatedObjectType | None:
        """
        Override the related object type to account for writing audit logs for related objects
        when certain events happen on this model.
        """
        return self.related_object_type

    def get_audit_log_identity(self) -> str:
        """Override the human-readable identity for the related object"""
        return str(self)

    def get_audit_log_model_name(self, history_instance) -> str:
        """Override the human-readable model name for the related object"""
        if related_object_type := self.get_audit_log_related_object_type(
            history_instance
        ):
            return related_object_type.value
        else:
            return self._meta.verbose_name or self.__class__.__name__

    def _get_organisations(self) -> typing.Iterable[Organisation] | None:
        """Return the related organisation for this model."""
        return None

    def _get_project(self) -> Project | None:
        """Return the related project for this model."""
        return None

    def _get_environment(self) -> Environment | None:
        """Return the related environment for this model."""
        return None


# TODO #2797 later: get IP address from request
def get_history_user(
    instance: typing.Any, request: HttpRequest
) -> typing.Optional["FFAdminUser"]:
    user = getattr(request, "user", None)
    return None if getattr(user, "is_master_api_key_user", False) else user


# remove this once django-simple-history > 3.4.0 is released
class HistoricalRecords(BaseHistoricalRecords):
    # patch https://github.com/jazzband/django-simple-history/pull/1218
    def create_historical_record_m2ms(self, history_instance, instance):
        for field in history_instance._history_m2m_fields:
            m2m_history_model = self.m2m_models[field]
            original_instance = history_instance.instance
            through_model = getattr(original_instance, field.name).through

            insert_rows = []

            # FIX IS HERE
            # `m2m_field_name()` is part of Django's internal API
            through_field_name = field.m2m_field_name()

            rows = through_model.objects.filter(**{through_field_name: instance})

            for row in rows:
                insert_row = {"history": history_instance}

                for through_model_field in through_model._meta.fields:
                    insert_row[through_model_field.name] = getattr(
                        row, through_model_field.name
                    )

                insert_rows.append(m2m_history_model(**insert_row))

            pre_create_historical_m2m_records.send(
                sender=m2m_history_model,
                rows=insert_rows,
                history_instance=history_instance,
                instance=instance,
                field=field,
            )
            created_rows = m2m_history_model.objects.bulk_create(insert_rows)
            post_create_historical_m2m_records.send(
                sender=m2m_history_model,
                created_rows=created_rows,
                history_instance=history_instance,
                instance=instance,
                field=field,
            )

    # patch https://github.com/jazzband/django-simple-history/pull/1243
    def get_m2m_fields_from_model(self, model):
        m2m_fields = set(self.m2m_fields)
        try:
            m2m_fields.update(getattr(model, self.m2m_fields_model_field_name))
        except AttributeError:
            pass
        # FIX IS HERE
        field_names = [
            field if isinstance(field, str) else field.name for field in m2m_fields
        ]
        return [getattr(model, field_name).field for field_name in field_names]

    # fix https://github.com/jazzband/django-simple-history/issues/1268
    def create_historical_record(self, instance, history_type, using=None):
        using = using if self.use_base_model_db else None
        history_date = getattr(instance, "_history_date", timezone.now())
        history_user = self.get_history_user(instance)
        history_change_reason = self.get_change_reason_for_object(
            instance, history_type, using
        )
        manager = getattr(instance, self.manager_name)

        attrs = {}
        # FIX IS HERE
        for field in manager.model.tracked_fields:
            attrs[field.attname] = getattr(instance, field.attname)

        relation_field = getattr(manager.model, "history_relation", None)
        if relation_field is not None:
            attrs["history_relation"] = instance

        history_instance = manager.model(
            history_date=history_date,
            history_type=history_type,
            history_user=history_user,
            history_change_reason=history_change_reason,
            **attrs,
        )

        pre_create_historical_record.send(
            sender=manager.model,
            instance=instance,
            history_date=history_date,
            history_user=history_user,
            history_change_reason=history_change_reason,
            history_instance=history_instance,
            using=using,
        )

        history_instance.save(using=using)
        self.create_historical_record_m2ms(history_instance, instance)

        post_create_historical_record.send(
            sender=manager.model,
            instance=instance,
            history_instance=history_instance,
            history_date=history_date,
            history_user=history_user,
            history_change_reason=history_change_reason,
            using=using,
        )

    # fix: should check settings
    def m2m_changed(self, instance, action, attr, pk_set, reverse, **_):
        # FIX IS HERE
        if not getattr(settings, "SIMPLE_HISTORY_ENABLED", True):
            return
        super().m2m_changed(instance, action, attr, pk_set, reverse)

    # fix: m2m fields not tracked when through model used directly
    def finalize(self, sender, **kwargs):
        super().finalize(sender, **kwargs)

        # repeat sender check from superclass
        inherited = False
        if self.cls is not sender:  # set in concrete
            inherited = self.inherit and issubclass(sender, self.cls)
            if not inherited:
                return  # set in abstract

        # connect additional m2m signal handlers
        for field in self.get_m2m_fields_from_model(sender):
            models.signals.post_save.connect(
                functools.partial(
                    self.post_m2m_save_or_delete,
                    cls=sender,
                    attr=field.name,
                ),
                sender=field.remote_field.through,
                weak=False,
            )
            models.signals.post_delete.connect(
                functools.partial(
                    self.post_m2m_save_or_delete,
                    cls=sender,
                    attr=field.name,
                    created=False,  # unused but required to match post_save signature
                ),
                sender=field.remote_field.through,
                weak=False,
            )

    def post_m2m_save_or_delete(self, instance, created, cls, attr, **kwargs):
        # call post_save on parent model
        instance_attr = cls._meta.get_field(attr).m2m_field_name()
        self.post_save(getattr(instance, instance_attr), False, **kwargs)


def default_get_create_log_message(
    self: _AbstractBaseAuditableModel, history_instance
) -> str | None:
    return CREATED_MESSAGE.format(
        model_name=self.get_audit_log_model_name(history_instance),
        identity=self.get_audit_log_identity(),
    )


def _get_action(model: _AbstractBaseAuditableModel, field: str) -> str:
    new_value = getattr(model, field)
    if new_value is True:
        return "set true"
    if new_value is False:
        return "set false"
    if new_value is None:
        return "set null"

    return "updated"


def default_get_update_log_message(
    self: _AbstractBaseAuditableModel, history_instance, delta: ModelDelta
) -> str | None:
    if not history_instance.prev_record:
        logger.warning(f"No previous record for {self}")
        return None

    model_name = self.get_audit_log_model_name(history_instance)
    identity = self.get_audit_log_identity()
    changed_fields = delta.changed_fields
    return (
        "; ".join(
            UPDATED_MESSAGE.format(
                model_name=model_name,
                identity=identity,
                field=field,
                action=_get_action(self, field),
            )
            for field in changed_fields
        )
        or None
    )


def default_get_delete_log_message(
    self: _AbstractBaseAuditableModel, history_instance
) -> str | None:
    return DELETED_MESSAGE.format(
        model_name=self.get_audit_log_model_name(history_instance),
        identity=self.get_audit_log_identity(),
    )


def abstract_base_auditable_model_factory(
    related_object_type: RelatedObjectType,
    unaudited_fields: typing.Sequence[str] | None = None,
    audited_m2m_fields: typing.Sequence[str] | None = None,
    audit_create=False,
    audit_update=False,
    audit_delete=False,
) -> typing.Type[_AbstractBaseAuditableModel]:
    class Base(_AbstractBaseAuditableModel):
        history = HistoricalRecords(
            bases=[BaseHistoricalModel],
            excluded_fields=unaudited_fields or (),
            m2m_fields=audited_m2m_fields or (),
            get_user=get_history_user,
            inherit=True,
        )

        class Meta:
            abstract = True

    Base.related_object_type = related_object_type
    if audit_create:
        Base.get_create_log_message = default_get_create_log_message
    if audit_update:
        Base.get_update_log_message = default_get_update_log_message
    if audit_delete:
        Base.get_delete_log_message = default_get_delete_log_message

    return Base


def register_auditable_model(
    model: type[models.Model],
    app: str,
    related_object_type: RelatedObjectType,
    unaudited_fields: typing.Sequence[str] | None = None,
    audited_m2m_fields: typing.Sequence[str] | None = None,
    *,
    audit_create=False,
    audit_update=False,
    audit_delete=False,
):
    register(
        model,
        app,
        bases=[BaseHistoricalModel],
        excluded_fields=unaudited_fields or (),
        m2m_fields=audited_m2m_fields or (),
        get_user=get_history_user,
    )

    for attr in _AbstractBaseAuditableModel.__dict__:
        try:
            getattr(model, attr)
        except AttributeError:
            setattr(model, attr, getattr(_AbstractBaseAuditableModel, attr))

    model.related_object_type = related_object_type
    if audit_create:
        model.get_create_log_message = default_get_create_log_message
    if audit_update:
        model.get_update_log_message = default_get_update_log_message
    if audit_delete:
        model.get_delete_log_message = default_get_delete_log_message
