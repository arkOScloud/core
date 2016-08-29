import unittest

from arkos import conns, connections
from arkos.system import users, groups, domains
from mockldap import MockLdap

from . import init_testing


class RolesTestCase(unittest.TestCase):
    directory = {
        "cn=admin,dc=arkos-servers,dc=org": {
            "objectClass": ["simpleSecurityObject", "organizationalRole"],
            "cn": ["admin"],
            "userPassword": ["{CRYPT}$6$DB6HMRCYVNXIW1S0$0niONOx5XS7c0MdUzAoJ1q8jmut4Bwmg14y3CAjo81dPJlX0NBwQB3XqknJh9JjTV44rOEesOV0/1/yZ6N4Qu/"]
        },
        "ou=users,dc=arkos-servers,dc=org": {
            "objectClass": ["organizationalUnit", "top"],
            "ou": ["users"]
        },
        "ou=domains,dc=arkos-servers,dc=org": {
            "objectClass": ["organizationalUnit", "top"],
            "ou": ["domains"]
        },
        "ou=groups,dc=arkos-servers,dc=org": {
            "objectClass": ["organizationalUnit", "top"],
            "ou": ["groups"]
        },
        "ou=sudo,dc=arkos-servers,dc=org": {
            "objectClass": ["organizationalUnit", "top"],
            "ou": ["sudo"]
        },
        "cn=admins,ou=groups,dc=arkos-servers,dc=org": {
            "objectClass": ["groupOfNames", "top"],
            "cn": ["admins"],
            "member": ["cn=admin,dc=arkos-servers,dc=org"]
        },
        "cn=admin,ou=sudo,dc=arkos-servers,dc=org": {
            "objectClass": ["sudoRole", "top"],
            "cn": ["admin"],
            "sudoUser": ["admin"],
            "sudoHost": ["ALL"],
            "sudoCommand": ["ALL"],
            "sudoOption": ["authenticate"]
        },
        "virtualdomain=localhost,ou=domains,dc=arkos-servers,dc=org": {
            "objectClass": ["mailDomain", "top"],
            "virtualdomain": ["localhost"]
        }
    }

    @classmethod
    def setUpClass(cls):
        cls.mockldap = MockLdap(cls.directory)
        cls.config, cls.secrets, cls.policies = init_testing()

    @classmethod
    def tearDownClass(cls):
        del cls.mockldap

    def setUp(self):
        self.mockldap.start()
        self.ldapobj = self.mockldap['ldap://localhost/']
        conns.LDAP = connections.ldap_connect(
            config=self.config, passwd=self.secrets.get("ldap"))

    def tearDown(self):
        self.mockldap.stop()
        del self.ldapobj

    def test_add_user(self):
        u = users.User(
            name="testuser", first_name="Test", last_name="User",
            domain="localhost", admin=True, sudo=False
        )
        u.add(passwd="testpass")
        u = users.get(name="testuser")
        self.assertIsNotNone(u)
        self.assertEqual(u.name, "testuser")
        self.assertEqual(u.first_name, "Test")
        self.assertEqual(u.last_name, "User")
        self.assertEqual(u.domain, "localhost")
        self.assertTrue(u.admin)
        self.assertFalse(u.sudo)

    def test_auth_success(self):
        u = users.User(
            name="testuser", first_name="Test", last_name="User",
            domain="localhost", admin=True, sudo=False
        )
        u.add(passwd="testpass")
        u = users.get(name="testuser")
        self.assertTrue(u.verify_passwd("testpass"))

    def test_auth_fail(self):
        u = users.User(
            name="testuser", first_name="Test", last_name="User",
            domain="localhost", admin=False, sudo=False
        )
        u.add(passwd="testpass")
        u = users.get(name="testuser")
        self.assertFalse(u.verify_passwd("testpass"))
