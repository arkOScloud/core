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
        _add_test_user("testuser")
        u = users.get(name="testuser")
        self.assertIsNotNone(u)
        self.assertEqual(u.name, "testuser")
        self.assertEqual(u.first_name, "Test")
        self.assertEqual(u.last_name, "User")
        self.assertEqual(u.domain, "localhost")
        self.assertTrue(u.admin)
        self.assertFalse(u.sudo)

    def test_upd_user(self):
        _add_test_user("testuser")
        u = users.get(name="testuser")
        u.first_name = "Notatest"
        u.last_name = ""
        u.update(newpasswd="mypass")
        u = users.get(name="testuser")
        self.assertEqual(u.first_name, "Notatest")
        self.assertEqual(u.last_name, "")
        self.assertTrue(u.verify_passwd("mypass"))

    def test_del_user(self):
        _add_test_user("testuser")
        u = users.get(name="testuser")
        u.delete()
        self.assertIsNone(users.get(name="testuser"))

    def test_auth_success(self):
        _add_test_user("testuser")
        u = users.get(name="testuser")
        self.assertTrue(u.verify_passwd("testpass"))

    def test_auth_fail(self):
        _add_test_user("testuser")
        u = users.get(name="testuser")
        self.assertFalse(u.verify_passwd("falsepass"))

    def test_add_group(self):
        _add_test_user("testuser1")
        g = groups.Group(
            name="testgroup", users=["testuser1"]
        )
        g.add()

    def test_upd_group(self):
        _add_test_user("testuser1")
        _add_test_user("testuser2")
        g = groups.Group(
            name="testgroup", users=["testuser1"]
        )
        g.add()
        g = groups.get(name="testgroup")
        g.users = ["testuser2"]
        g.update()
        g = groups.get(name="testgroup")
        self.assertEqual(g.users, ["testuser2"])

    def test_del_group(self):
        g = groups.Group(name="testgroup", users=[])
        g.add()
        g = groups.get(name="testgroup")
        g.delete()
        self.assertIsNone(groups.get(name="testgroup"))

    def test_add_domain(self):
        d = domains.Domain("testdomain.xyz")
        d.add()
        self.assertIsNotNone(domains.get("testdomain.xyz"))

    def test_del_domain(self):
        d = domains.Domain("testdomain.xyz")
        d.add()
        d = domains.get("testdomain.xyz")
        d.remove()
        self.assertIsNone(domains.get("testdomain.xyz"))


def _add_test_user(uname):
    u = users.User(
        name=uname, first_name="Test", last_name="User",
        domain="localhost", admin=True, sudo=False
    )
    u.add(passwd="testpass")
