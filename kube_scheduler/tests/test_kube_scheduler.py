# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import os
import pytest
import mock

from datadog_checks.base.checks.kube_leader import ElectionRecord
from datadog_checks.kube_scheduler import KubeSchedulerCheck

instance = {
    'prometheus_url': 'http://localhost:10251/metrics',
    'send_histograms_buckets': True,
}

# Constants
CHECK_NAME = 'kube_scheduler'
NAMESPACE = 'kube_scheduler'


@pytest.fixture()
def mock_metrics():
    f_name = os.path.join(os.path.dirname(__file__), 'fixtures', 'metrics.txt')
    with open(f_name, 'r') as f:
        text_data = f.read()
    with mock.patch(
        'requests.get',
        return_value=mock.MagicMock(
            status_code=200,
            iter_lines=lambda **kwargs: text_data.split("\n"),
            headers={'Content-Type': "text/plain"}
        ),
    ):
        yield


@pytest.fixture()
def mock_leader():
    # Inject a fake object in the leader-election monitoring logic
    with mock.patch(
        'datadog_checks.kube_scheduler.KubeSchedulerCheck._get_record',
        return_value=ElectionRecord(
            '{"holderIdentity":"pod1","leaseDurationSeconds":15,"leaderTransitions":3,' +
            '"acquireTime":"2018-12-19T18:23:24Z","renewTime":"2019-01-02T16:30:07Z"}'
        ),
    ):
        yield


def test_check_metrics(aggregator, mock_metrics, mock_leader):
    c = KubeSchedulerCheck(CHECK_NAME, None, {}, [instance])
    c.check(instance)

    def assert_metric(name, **kwargs):
        # Wrapper to keep assertions < 120 chars
        aggregator.assert_metric(NAMESPACE + name, **kwargs)

    for metric_name in aggregator.metric_names:
        print aggregator.metrics(metric_name)

    assert_metric('.go.goroutines')
    assert_metric('.go.threads')
    assert_metric('.process.open_fds')
    assert_metric('.client.http.requests')
    assert_metric('.process.max_fds')

    assert_metric('.apiserver.audit.event.count', value=0.0, tags=[])
    assert_metric('.http.response.size_bytes.quantile', value=32063.0, tags=['quantile:0.5', 'handler:prometheus'])
    assert_metric('.volume_scheduling_duration.count',
                  value=15.0, tags=['operation:predicate', 'upper_bound:1024000.0'])
    # check summary transformation from microsecond to second
    assert_metric('.http.request.duration.sum', value=0.48679200000000006, tags=['handler:prometheus'])
    # check historgram transformation from microsecond to second
    assert_metric('.scheduling.algorithm_duration.sum', value=0.06377, tags=[])
    # Leader election mixin
    # expected_le_tags = [
    #   "record_kind:endpoints",
    #   "record_name:kube-scheduler",
    #   "record_namespace:kube-system"
    # ]
    # assert_metric('.leader_election.transitions', value=3, tags=[])
    # assert_metric('.leader_election.lease_duration', value=15, tags=expected_le_tags)
