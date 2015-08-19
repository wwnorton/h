# -*- coding: utf-8 -*-
import logging

from h.api.models import Annotation
from h.api import search as search_lib


log = logging.getLogger(__name__)


# These annotation fields are not to be set by the user.
PROTECTED_FIELDS = ['created', 'updated', 'user', 'consumer', 'id']


def search_annotations(params, user, search_normalized_uris=False):
    results = search_lib.search(request_params=params,
                                user=user,
                                search_normalized_uris=search_normalized_uris)

    return {
        'total': results['total'],
        'rows': [search_lib.render(a) for a in results['rows']],
    }


def create_annotation(fields, user):
    """Create and store an annotation."""
    # Some fields are not to be set by the user, ignore them
    for field in PROTECTED_FIELDS:
        fields.pop(field, None)

    # Create Annotation instance
    annotation = Annotation(fields)

    annotation['user'] = user.id
    annotation['consumer'] = user.consumer.key


    # Save it in the database
    search_lib.prepare(annotation)
    annotation.save()

    log.debug('Created annotation; user: %s, consumer key: %s',
              annotation['user'], annotation['consumer'])

    return annotation


def _anonymize_deletes(annotation):
    """Clear the author and remove the user from the annotation permissions."""
    # Delete the annotation author, if present
    user = annotation.pop('user')

    # Remove the user from the permissions, but keep any others in place.
    permissions = annotation.get('permissions', {})
    for action in permissions.keys():
        filtered = [
            role
            for role in annotation['permissions'][action]
            if role != user
        ]
        annotation['permissions'][action] = filtered


def update_annotation(annotation, fields, has_admin_permission):
    # Some fields are not to be set by the user, ignore them
    for field in PROTECTED_FIELDS:
        fields.pop(field, None)

    # If the user is changing access permissions, check if it's allowed.
    changing_permissions = (
        'permissions' in fields and
        fields['permissions'] != annotation.get('permissions', {})
    )
    if changing_permissions and not has_admin_permission:
        raise RuntimeError("Not authorized to change annotation permissions.",
                           401)  # Unauthorized

    # Update the annotation with the new data
    annotation.update(fields)

    # If the annotation is flagged as deleted, remove mentions of the user
    if annotation.get('deleted', False):
        _anonymize_deletes(annotation)

    # Save the annotation in the database, overwriting the old version.
    search_lib.prepare(annotation)
    annotation.save()
