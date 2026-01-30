# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import unittest
from unittest import mock

from azure.cli.command_modules.acr.network_rule import (
    acr_network_rule_list,
    acr_network_rule_add,
    acr_network_rule_remove,
    _get_registry_url,
    _format_registry_response,
    API_VERSION
)


class MockResponse:
    """Mock response object for send_raw_request."""
    def __init__(self, json_data):
        self._json_data = json_data

    def json(self):
        return self._json_data


def _get_mock_registry_response(network_rule_set=None):
    """Create a mock registry response."""
    if network_rule_set is None:
        network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [],
            'ipRules': []
        }
    return {
        'id': '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/myRG/providers/Microsoft.ContainerRegistry/registries/myRegistry',
        'name': 'myRegistry',
        'type': 'Microsoft.ContainerRegistry/registries',
        'location': 'westus',
        'tags': {},
        'sku': {'name': 'Premium', 'tier': 'Premium'},
        'properties': {
            'provisioningState': 'Succeeded',
            'networkRuleSet': network_rule_set
        }
    }


class TestGetRegistryUrl(unittest.TestCase):
    """Tests for _get_registry_url function."""

    @mock.patch('azure.cli.command_modules.acr.network_rule.get_subscription_id')
    def test_get_registry_url(self, mock_get_sub):
        mock_get_sub.return_value = '00000000-0000-0000-0000-000000000000'
        mock_cli_ctx = mock.MagicMock()

        url = _get_registry_url(mock_cli_ctx, 'myResourceGroup', 'myRegistry')

        expected_url = (
            '/subscriptions/00000000-0000-0000-0000-000000000000/'
            'resourceGroups/myResourceGroup/'
            'providers/Microsoft.ContainerRegistry/registries/myRegistry'
            f'?api-version={API_VERSION}'
        )
        self.assertEqual(url, expected_url)
        mock_get_sub.assert_called_once_with(mock_cli_ctx)


class TestFormatRegistryResponse(unittest.TestCase):
    """Tests for _format_registry_response function."""

    def test_format_registry_response_empty_rules(self):
        response = _get_mock_registry_response()
        result = _format_registry_response(response)

        self.assertEqual(result['name'], 'myRegistry')
        self.assertEqual(result['provisioningState'], 'Succeeded')
        self.assertEqual(result['networkRuleSet']['defaultAction'], 'Deny')
        self.assertEqual(result['networkRuleSet']['virtualNetworkRules'], [])
        self.assertEqual(result['networkRuleSet']['ipRules'], [])

    def test_format_registry_response_with_vnet_rules(self):
        network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [
                {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1', 'action': 'Allow'},
                {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet2', 'action': 'Allow'}
            ],
            'ipRules': []
        }
        response = _get_mock_registry_response(network_rule_set)
        result = _format_registry_response(response)

        self.assertEqual(len(result['networkRuleSet']['virtualNetworkRules']), 2)
        self.assertEqual(
            result['networkRuleSet']['virtualNetworkRules'][0]['virtualNetworkResourceId'],
            '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1'
        )
        self.assertEqual(result['networkRuleSet']['virtualNetworkRules'][0]['action'], 'Allow')

    def test_format_registry_response_with_ip_rules(self):
        network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [],
            'ipRules': [
                {'ipAddressOrRange': '10.0.0.0/24', 'action': 'Allow'},
                {'ipAddressOrRange': '192.168.1.1', 'action': 'Allow'}
            ]
        }
        response = _get_mock_registry_response(network_rule_set)
        result = _format_registry_response(response)

        self.assertEqual(len(result['networkRuleSet']['ipRules']), 2)
        self.assertEqual(result['networkRuleSet']['ipRules'][0]['ipAddressOrRange'], '10.0.0.0/24')


class TestAcrNetworkRuleList(unittest.TestCase):
    """Tests for acr_network_rule_list function."""

    @mock.patch('azure.cli.command_modules.acr.network_rule.send_raw_request')
    @mock.patch('azure.cli.command_modules.acr.network_rule.validate_premium_registry')
    @mock.patch('azure.cli.command_modules.acr.network_rule.get_subscription_id')
    def test_list_empty_rules(self, mock_get_sub, mock_validate, mock_send_request):
        mock_get_sub.return_value = '00000000-0000-0000-0000-000000000000'
        mock_validate.return_value = (mock.MagicMock(), 'myResourceGroup')
        mock_send_request.return_value = MockResponse(_get_mock_registry_response())

        mock_cmd = mock.MagicMock()

        result = acr_network_rule_list(mock_cmd, 'myRegistry', 'myResourceGroup')

        self.assertEqual(result['virtualNetworkRules'], [])
        self.assertEqual(result['ipRules'], [])
        self.assertNotIn('defaultAction', result)

    @mock.patch('azure.cli.command_modules.acr.network_rule.send_raw_request')
    @mock.patch('azure.cli.command_modules.acr.network_rule.validate_premium_registry')
    @mock.patch('azure.cli.command_modules.acr.network_rule.get_subscription_id')
    def test_list_with_rules(self, mock_get_sub, mock_validate, mock_send_request):
        mock_get_sub.return_value = '00000000-0000-0000-0000-000000000000'
        mock_validate.return_value = (mock.MagicMock(), 'myResourceGroup')

        network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [
                {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1', 'action': 'Allow'}
            ],
            'ipRules': [
                {'ipAddressOrRange': '10.0.0.0/24', 'action': 'Allow'}
            ]
        }
        mock_send_request.return_value = MockResponse(_get_mock_registry_response(network_rule_set))

        mock_cmd = mock.MagicMock()

        result = acr_network_rule_list(mock_cmd, 'myRegistry', 'myResourceGroup')

        self.assertEqual(len(result['virtualNetworkRules']), 1)
        self.assertEqual(
            result['virtualNetworkRules'][0]['virtualNetworkResourceId'],
            '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1'
        )
        self.assertEqual(len(result['ipRules']), 1)
        self.assertEqual(result['ipRules'][0]['ipAddressOrRange'], '10.0.0.0/24')


class TestAcrNetworkRuleAdd(unittest.TestCase):
    """Tests for acr_network_rule_add function."""

    @mock.patch('azure.cli.command_modules.acr.network_rule.send_raw_request')
    @mock.patch('azure.cli.command_modules.acr.network_rule.validate_premium_registry')
    @mock.patch('azure.cli.command_modules.acr.network_rule.get_subscription_id')
    def test_add_ip_rule(self, mock_get_sub, mock_validate, mock_send_request):
        mock_get_sub.return_value = '00000000-0000-0000-0000-000000000000'
        mock_validate.return_value = (mock.MagicMock(), 'myResourceGroup')

        # First call returns current registry, second call returns updated registry
        updated_network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [],
            'ipRules': [{'ipAddressOrRange': '10.0.0.0/24', 'action': 'Allow'}]
        }
        mock_send_request.side_effect = [
            MockResponse(_get_mock_registry_response()),
            MockResponse(_get_mock_registry_response(updated_network_rule_set))
        ]

        mock_cmd = mock.MagicMock()

        result = acr_network_rule_add(
            mock_cmd, None, 'myRegistry',
            ip_address='10.0.0.0/24',
            resource_group_name='myResourceGroup'
        )

        self.assertEqual(result['name'], 'myRegistry')
        self.assertEqual(result['provisioningState'], 'Succeeded')
        self.assertEqual(len(result['networkRuleSet']['ipRules']), 1)
        self.assertEqual(result['networkRuleSet']['ipRules'][0]['ipAddressOrRange'], '10.0.0.0/24')

        # Verify PATCH was called with correct payload
        self.assertEqual(mock_send_request.call_count, 2)
        patch_call = mock_send_request.call_args_list[1]
        self.assertEqual(patch_call[0][1], 'PATCH')

    @mock.patch('azure.cli.command_modules.acr.network_rule._validate_subnet')
    @mock.patch('azure.cli.command_modules.acr.network_rule.send_raw_request')
    @mock.patch('azure.cli.command_modules.acr.network_rule.validate_premium_registry')
    @mock.patch('azure.cli.command_modules.acr.network_rule.get_subscription_id')
    def test_add_vnet_rule(self, mock_get_sub, mock_validate, mock_send_request, mock_validate_subnet):
        mock_get_sub.return_value = '00000000-0000-0000-0000-000000000000'
        mock_validate.return_value = (mock.MagicMock(), 'myResourceGroup')
        mock_validate_subnet.return_value = '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1'

        updated_network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [
                {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1', 'action': 'Allow'}
            ],
            'ipRules': []
        }
        mock_send_request.side_effect = [
            MockResponse(_get_mock_registry_response()),
            MockResponse(_get_mock_registry_response(updated_network_rule_set))
        ]

        mock_cmd = mock.MagicMock()

        result = acr_network_rule_add(
            mock_cmd, None, 'myRegistry',
            subnet='subnet1',
            vnet_name='vnet',
            resource_group_name='myResourceGroup'
        )

        self.assertEqual(result['name'], 'myRegistry')
        self.assertEqual(len(result['networkRuleSet']['virtualNetworkRules']), 1)
        self.assertEqual(
            result['networkRuleSet']['virtualNetworkRules'][0]['virtualNetworkResourceId'],
            '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1'
        )


class TestAcrNetworkRuleRemove(unittest.TestCase):
    """Tests for acr_network_rule_remove function."""

    @mock.patch('azure.cli.command_modules.acr.network_rule.send_raw_request')
    @mock.patch('azure.cli.command_modules.acr.network_rule.validate_premium_registry')
    @mock.patch('azure.cli.command_modules.acr.network_rule.get_subscription_id')
    def test_remove_ip_rule(self, mock_get_sub, mock_validate, mock_send_request):
        mock_get_sub.return_value = '00000000-0000-0000-0000-000000000000'
        mock_validate.return_value = (mock.MagicMock(), 'myResourceGroup')

        initial_network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [],
            'ipRules': [
                {'ipAddressOrRange': '10.0.0.0/24', 'action': 'Allow'},
                {'ipAddressOrRange': '192.168.1.0/24', 'action': 'Allow'}
            ]
        }
        updated_network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [],
            'ipRules': [{'ipAddressOrRange': '192.168.1.0/24', 'action': 'Allow'}]
        }
        mock_send_request.side_effect = [
            MockResponse(_get_mock_registry_response(initial_network_rule_set)),
            MockResponse(_get_mock_registry_response(updated_network_rule_set))
        ]

        mock_cmd = mock.MagicMock()

        result = acr_network_rule_remove(
            mock_cmd, None, 'myRegistry',
            ip_address='10.0.0.0/24',
            resource_group_name='myResourceGroup'
        )

        self.assertEqual(result['name'], 'myRegistry')
        self.assertEqual(len(result['networkRuleSet']['ipRules']), 1)
        self.assertEqual(result['networkRuleSet']['ipRules'][0]['ipAddressOrRange'], '192.168.1.0/24')

    @mock.patch('azure.cli.command_modules.acr.network_rule._validate_subnet')
    @mock.patch('azure.cli.command_modules.acr.network_rule.send_raw_request')
    @mock.patch('azure.cli.command_modules.acr.network_rule.validate_premium_registry')
    @mock.patch('azure.cli.command_modules.acr.network_rule.get_subscription_id')
    def test_remove_vnet_rule(self, mock_get_sub, mock_validate, mock_send_request, mock_validate_subnet):
        mock_get_sub.return_value = '00000000-0000-0000-0000-000000000000'
        mock_validate.return_value = (mock.MagicMock(), 'myResourceGroup')

        subnet_id = '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1'
        mock_validate_subnet.return_value = subnet_id

        initial_network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [
                {'id': subnet_id, 'action': 'Allow'},
                {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet2', 'action': 'Allow'}
            ],
            'ipRules': []
        }
        updated_network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [
                {'id': '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet2', 'action': 'Allow'}
            ],
            'ipRules': []
        }
        mock_send_request.side_effect = [
            MockResponse(_get_mock_registry_response(initial_network_rule_set)),
            MockResponse(_get_mock_registry_response(updated_network_rule_set))
        ]

        mock_cmd = mock.MagicMock()

        result = acr_network_rule_remove(
            mock_cmd, None, 'myRegistry',
            subnet='subnet1',
            vnet_name='vnet',
            resource_group_name='myResourceGroup'
        )

        self.assertEqual(result['name'], 'myRegistry')
        self.assertEqual(len(result['networkRuleSet']['virtualNetworkRules']), 1)
        self.assertEqual(
            result['networkRuleSet']['virtualNetworkRules'][0]['virtualNetworkResourceId'],
            '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet2'
        )

    @mock.patch('azure.cli.command_modules.acr.network_rule._validate_subnet')
    @mock.patch('azure.cli.command_modules.acr.network_rule.send_raw_request')
    @mock.patch('azure.cli.command_modules.acr.network_rule.validate_premium_registry')
    @mock.patch('azure.cli.command_modules.acr.network_rule.get_subscription_id')
    def test_remove_vnet_rule_case_insensitive(self, mock_get_sub, mock_validate, mock_send_request, mock_validate_subnet):
        """Test that VNet rule removal is case-insensitive."""
        mock_get_sub.return_value = '00000000-0000-0000-0000-000000000000'
        mock_validate.return_value = (mock.MagicMock(), 'myResourceGroup')

        # Return lowercase subnet ID from validation
        subnet_id_lower = '/subscriptions/sub/resourcegroups/rg/providers/microsoft.network/virtualnetworks/vnet/subnets/subnet1'
        mock_validate_subnet.return_value = subnet_id_lower

        # Registry has uppercase subnet ID
        subnet_id_mixed = '/subscriptions/SUB/resourceGroups/RG/providers/Microsoft.Network/virtualNetworks/VNET/subnets/SUBNET1'
        initial_network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [{'id': subnet_id_mixed, 'action': 'Allow'}],
            'ipRules': []
        }
        updated_network_rule_set = {
            'defaultAction': 'Deny',
            'virtualNetworkRules': [],
            'ipRules': []
        }
        mock_send_request.side_effect = [
            MockResponse(_get_mock_registry_response(initial_network_rule_set)),
            MockResponse(_get_mock_registry_response(updated_network_rule_set))
        ]

        mock_cmd = mock.MagicMock()

        result = acr_network_rule_remove(
            mock_cmd, None, 'myRegistry',
            subnet='subnet1',
            vnet_name='vnet',
            resource_group_name='myResourceGroup'
        )

        # Rule should be removed even with case mismatch
        self.assertEqual(result['networkRuleSet']['virtualNetworkRules'], [])


if __name__ == '__main__':
    unittest.main()
