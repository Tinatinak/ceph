# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json


from . import ApiController, Endpoint, BaseController
from .. import mgr
from ..security import Permission, Scope
from ..controllers.rbd_mirroring import get_daemons_and_pools
from ..exceptions import ViewCacheNoDataException
from ..tools import TaskManager


@ApiController('/summary')
class Summary(BaseController):
    def _health_status(self):
        health_data = mgr.get("health")
        return json.loads(health_data["json"])['status']

    def _rbd_mirroring(self):
        try:
            _, data = get_daemons_and_pools()
        except ViewCacheNoDataException:
            return {}

        daemons = data.get('daemons', [])
        pools = data.get('pools', {})

        warnings = 0
        errors = 0
        for daemon in daemons:
            if daemon['health_color'] == 'error':
                errors += 1
            elif daemon['health_color'] == 'warning':
                warnings += 1
        for _, pool in pools.items():
            if pool['health_color'] == 'error':
                errors += 1
            elif pool['health_color'] == 'warning':
                warnings += 1
        return {'warnings': warnings, 'errors': errors}

    @Endpoint()
    def __call__(self):
        executing_t, finished_t = TaskManager.list_serializable()
        executing_tasks = []
        for t in executing_t:
            if self.validate_task_permissions(t['name']):
                executing_tasks.append(t)
        finished_tasks = []
        for t in finished_t:
            if self.validate_task_permissions(t['name']):
                finished_tasks.append(t)

        result = {
            'health_status': self._health_status(),
            'mgr_id': mgr.get_mgr_id(),
            'have_mon_connection': mgr.have_mon_connection(),
            'executing_tasks': executing_tasks,
            'finished_tasks': finished_tasks,
            'version': mgr.version
        }
        if self._has_permissions(Permission.READ, Scope.RBD_MIRRORING):
            result['rbd_mirroring'] = self._rbd_mirroring()
        return result

    def validate_task_permissions(self, name):
        result = True
        if name == 'pool/create':
            result = self._has_permissions(Permission.CREATE, Scope.POOL)
        elif name == 'pool/edit':
            result = self._has_permissions(Permission.UPDATE, Scope.POOL)
        elif name == 'pool/delete':
            result = self._has_permissions(Permission.DELETE, Scope.POOL)
        elif name in [
                'rbd/create', 'rbd/copy', 'rbd/flatten',
                'rbd/snap/create', 'rbd/clone', 'rbd/snap/rollback',
                'rbd/trash/move', 'rbd/trash/restore', 'rbd/trash/purge'
            ]:
            result = self._has_permissions(Permission.CREATE, Scope.RBD_IMAGE)
        elif name in ['rbd/edit', 'rbd/snap/edit']:
            result = self._has_permissions(Permission.UPDATE, Scope.RBD_IMAGE)
        elif name in ['rbd/delete', 'rbd/snap/delete', 'rbd/trash/remove']:
            result = self._has_permissions(Permission.DELETE, Scope.RBD_IMAGE)

        return result
