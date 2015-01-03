import ConfigParser
import git
import glob
import os
import nginx
import re
import shutil

from arkos.core import Framework
from arkos.core.utility import dictfilter, shell, random_string


class Sites(Framework):
    REQUIRES = ["apps", "filesystems", "site_engines"]

    def on_init(self):
        self.site_dir = self.app.conf.get("websites", "site_dir")
        if not os.path.exists(self.site_dir):
            os.mkdir(self.site_dir)
        if not os.path.exists('/etc/nginx/sites-available'):
            os.makedirs('/etc/nginx/sites-available')
        if not os.path.exists('/etc/nginx/sites-enabled'):
            os.makedirs('/etc/nginx/sites-enabled')
        self.services.enable("nginx")

    def get_types(self):
        return self.apps.get(type="website")

    def get(self, **kwargs):
        sites = []
        if self.app.storage:
            sites = self.app.storage.get_list("websites")
        if not self.app.storage or not sites:
            sites = self.scan_sites()
        if self.app.storage:
            self.app.storage.append_all("websites", sites)
        return dictfilter(sites, kwargs)

    def scan_sites(self):
        sites = []
        for site in glob.glob('/etc/nginx/sites-available/.*.ginf'):
            g = ConfigParser.SafeConfigParser()
            g.read(site)
            path = os.path.join('/etc/nginx/sites-available', g.get('website', 'name'))
            if not os.path.exists(path):
                continue
            rport = re.compile('(\\d+)\s*(.*)')
            w = {"name": g.get('website', 'name'), "path": path}
            
            # Get actual values
            try:
                c = nginx.loadf(w["path"])
                stype = g.get('website', 'stype')
                w["type"] = stype if stype in [x["website_plugin"] for x in self.Apps.get_types()] else 'Unknown'
                # Get the right serverblock - SSL if it's here
                for x in c.servers:
                    if 'ssl' in x.filter('Key', 'listen')[0].value:
                        w["ssl"] = True
                        s = x
                        break
                else:
                    s = c.servers[0]
                w["port"], w["ssl"] = re.match(rport, s.filter('Key', 'listen')[0].value).group(1, 2)
                w["port"] = int(w["port"])
                w["addr"] = s.filter('Key', 'server_name')[0].value
                w["path"] = s.filter('Key', 'root')[0].value
                w["php"] = 'php' in s.filter('Key', 'index')[0].value
            except IndexError:
                pass
            w["version"] = g.get('website', 'version', None)
            w["dbengine"] = g.get('website', 'dbengine', None)
            w["dbname"] = g.get('website', 'dbname', None)
            w["dbuser"] = g.get('website', 'dbuser', None)
            w["enabled"] = True if os.path.exists(os.path.join('/etc/nginx/sites-enabled', g.get('website', 'name'))) else False
            w["meta"] = self.apps.get(id=w["type"])
            sites.append(w)
        return sites

    def nginx_add(self, site, add):
        if not site["path"]:
            site["path"] = os.path.join(self.site_dir, site["name"])
        c = nginx.Conf()
        s = nginx.Server(
            nginx.Key('listen', site["port"]),
            nginx.Key('server_name', site["addr"]),
            nginx.Key('root', site["path"]),
            nginx.Key('index', 'index.'+('php' if site["php"] else 'html'))
        )
        if add:
            s.add(*[x for x in add])
        c.add(s)
        nginx.dumpf(c, os.path.join('/etc/nginx/sites-available', site["name"]))
        # Write configuration file with info Genesis needs to know the site
        c = ConfigParser.SafeConfigParser()
        c.add_section('website')
        c.set('website', 'name', site["name"])
        c.set('website', 'stype', site["type"])
        c.set('website', 'ssl', '')
        c.set('website', 'version', site["version"] or 'None')
        c.set('website', 'dbengine', site["dbengine"] or '')
        c.set('website', 'dbname', site["dbname"] or '')
        c.set('website', 'dbuser', site["dbuser"] or '')
        with open(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'), 'w') as f:
            c.write(f)

    def nginx_edit(self, oldsite, site):
        # Update the nginx serverblock
        c = nginx.loadf(os.path.join('/etc/nginx/sites-available', oldsite["name"]))
        s = c.servers[0]
        if oldsite["ssl"] and oldsite["port"] == 443:
            for x in c.servers:
                if x.filter('Key', 'listen')[0].value == '443 ssl':
                    s = x
            if site["port"] != 443:
                for x in c.servers:
                    if not 'ssl' in x.filter('Key', 'listen')[0].value \
                    and x.filter('key', 'return'):
                        c.remove(x)
        elif site["port"] == 443:
            c.add(nginx.Server(
                nginx.Key('listen', '80'),
                nginx.Key('server_name', site["addr"]),
                nginx.Key('return', '301 https://%s$request_uri'%site["addr"])
            ))
        # If the name was changed, rename the folder and files
        if site["name"] != oldsite["name"]:
            if site["path"].endswith('_site'):
                site["path"] = os.path.join(self.site_dir, site["name"], '_site')
            elif site["path"].endswith('htdocs'):
                site["path"] = os.path.join(self.site_dir, site["name"], 'htdocs')
            else:
                site["path"] = os.path.join(self.site_dir, site["name"])
            g = ConfigParser.SafeConfigParser()
            g.read(os.path.join('/etc/nginx/sites-available', '.'+oldsite["name"]+'.ginf'))
            g.set('website', 'name', site["name"])
            with open(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'), 'w') as f:
                g.write(f)
            os.unlink(os.path.join('/etc/nginx/sites-available', '.'+oldsite["name"]+'.ginf'))
            if os.path.exists(os.path.join(self.site_dir, site["name"])):
                shutil.rmtree(os.path.join(self.site_dir, site["name"]))
            shutil.move(os.path.join(self.site_dir, oldsite["name"]), 
                os.path.join(self.site_dir, site["name"]))
            shutil.move(os.path.join('/etc/nginx/sites-available', oldsite["name"]),
                os.path.join('/etc/nginx/sites-available', site["name"]))
            self.nginx_disable(oldsite, reload=False)
            self.nginx_enable(site, reload=False)
        s.filter('Key', 'listen')[0].value = str(site["port"])+' ssl' if site["ssl"] else str(site["port"])
        s.filter('Key', 'server_name')[0].value = site["addr"]
        s.filter('Key', 'root')[0].value = site["path"]
        s.filter('Key', 'index')[0].value = 'index.php' if site["php"] else 'index.html'
        nginx.dumpf(c, os.path.join('/etc/nginx/sites-available', oldsite["name"]))
        self.nginx_reload()

    def nginx_remove(self, site, reload=True):
        try:
            self.nginx_disable(site, reload)
        except:
            pass
        os.unlink(os.path.join('/etc/nginx/sites-available', site["name"]))
        os.unlink(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'))

    def nginx_enable(self, site, reload=True):
        origin = os.path.join('/etc/nginx/sites-available', site["name"])
        target = os.path.join('/etc/nginx/sites-enabled', site["name"])
        if not os.path.exists(target):
            os.symlink(origin, target)
        if reload == True:
            self.nginx_reload()

    def nginx_disable(self, site, reload=True):
        os.unlink(os.path.join('/etc/nginx/sites-enabled', site["name"]))
        if reload == True:
            self.nginx_reload()

    def nginx_reload(self):
        status = shell('systemctl restart nginx')
        if status["code"] >= 1:
            raise ReloadError('nginx failed to reload.', "Edit")

    def php_enable(self):
        shell('sed -i "s/.*include \/etc\/nginx\/php.conf.*/\tinclude \/etc\/nginx\/php.conf;/" /etc/nginx/nginx.conf')

    def php_disable(self):
        shell('sed -i "s/.*include \/etc\/nginx\/php.conf.*/\t#include \/etc\/nginx\/php.conf;/" /etc/nginx/nginx.conf')

    def php_reload(self):
        status = shell('systemctl restart php-fpm')
        if status["code"] >= 1:
            raise Exception('PHP FastCGI failed to reload.')

    def ssl_enable(self, app, site, cname, cpath, kpath):
        # If no cipher preferences set, use the default ones
        # As per Mozilla recommendations, but substituting 3DES for RC4
        webapp = self.site_engines.get(app["pid"])
        ciphers = ':'.join([
            'ECDHE-RSA-AES128-GCM-SHA256', 'ECDHE-ECDSA-AES128-GCM-SHA256',
            'ECDHE-RSA-AES256-GCM-SHA384', 'ECDHE-ECDSA-AES256-GCM-SHA384',
            'kEDH+AESGCM', 'ECDHE-RSA-AES128-SHA256', 
            'ECDHE-ECDSA-AES128-SHA256', 'ECDHE-RSA-AES128-SHA', 
            'ECDHE-ECDSA-AES128-SHA', 'ECDHE-RSA-AES256-SHA384',
            'ECDHE-ECDSA-AES256-SHA384', 'ECDHE-RSA-AES256-SHA', 
            'ECDHE-ECDSA-AES256-SHA', 'DHE-RSA-AES128-SHA256',
            'DHE-RSA-AES128-SHA', 'DHE-RSA-AES256-SHA256', 
            'DHE-DSS-AES256-SHA', 'AES128-GCM-SHA256', 'AES256-GCM-SHA384',
            'ECDHE-RSA-DES-CBC3-SHA', 'ECDHE-ECDSA-DES-CBC3-SHA',
            'EDH-RSA-DES-CBC3-SHA', 'EDH-DSS-DES-CBC3-SHA', 
            'DES-CBC3-SHA', 'HIGH', '!aNULL', '!eNULL', '!EXPORT', '!DES',
            '!RC4', '!MD5', '!PSK'
            ])
        if self.app.conf.get("certificates", "ciphers"):
            ciphers = self.app.conf.get("certificates", "ciphers")
        else:
            self.app.conf.set("certificates", "ciphers", ciphers)
            self.app.conf.save()

        c = nginx.loadf(os.path.join('/etc/nginx/sites-available/', site["name"]))
        s = c.servers[0]
        l = s.filter('Key', 'listen')[0]
        if l.value == '80':
            l.value = '443 ssl'
            c.add(nginx.Server(
                nginx.Key('listen', '80'),
                nginx.Key('server_name', data.addr),
                nginx.Key('return', '301 https://%s$request_uri' % site["addr"])
            ))
            for x in c.servers:
                if x.filter('Key', 'listen')[0].value == '443 ssl':
                    s = x
                    break
        else:
            l.value = l.value.split(' ssl')[0] + ' ssl'
        for x in s.all():
            if type(x) == nginx.Key and x.name.startswith('ssl_'):
                s.remove(x)
        s.add(
            nginx.Key('ssl_certificate', cpath),
            nginx.Key('ssl_certificate_key', kpath),
            nginx.Key('ssl_protocols', 'TLSv1 TLSv1.1 TLSv1.2'),
            nginx.Key('ssl_ciphers', ciphers),
            nginx.Key('ssl_session_timeout', '5m'),
            nginx.Key('ssl_prefer_server_ciphers', 'on'),
            nginx.Key('ssl_session_cache', 'shared:SSL:50m'),
            )
        g = ConfigParser.SafeConfigParser()
        g.read(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'))
        g.set('website', 'ssl', cname)
        with open(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'), 'w') as f:
            g.write(f)
        nginx.dumpf(c, os.path.join('/etc/nginx/sites-available/', site["name"]))
        webapp.ssl_enable(os.path.join(self.site_dir, site["name"]), cpath, kpath)

    def ssl_disable(self, app, site):
        webapp = self.site_engines.get(app["pid"])
        c = nginx.loadf(os.path.join('/etc/nginx/sites-available/', site["name"]))
        if len(c.servers) > 1:
            for x in c.servers:
                if not 'ssl' in x.filter('Key', 'listen')[0].value \
                and x.filter('key', 'return'):
                    c.remove(x)
                    break
        s = c.servers[0]
        l = s.filter('Key', 'listen')[0]
        if l.value == '443 ssl':
            l.value = '80'
        else:
            l.value = l.value.rstrip(' ssl')
        s.remove(*[x for x in s.filter('Key') if x.name.startswith('ssl_')])
        g = ConfigParser.SafeConfigParser()
        g.read(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'))
        g.set('website', 'ssl', '')
        with open(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'), 'w') as f:
            g.write(f)
        nginx.dumpf(c, os.path.join('/etc/nginx/sites-available/', site["name"]))
        webapp.ssl_disable(os.path.join(self.site_dir, site["name"]))

    def install(self, app, vars, dbinfo={}, enable=True):
        specialmsg = ''
        site_dir = self.app.conf.get("websites", "site_dir")
        name = vars["name"].lower()
        webapp = self.site_engines.get(app["pid"])

        if not app["download_url"]:
            ending = ''
        elif app["download_url"].endswith('.tar.gz'):
            ending = '.tar.gz'
        elif app["download_url"].endswith('.tgz'):
            ending = '.tgz'
        elif app["download_url"].endswith('.tar.bz2'):
            ending = '.tar.bz2'
        elif app["download_url"].endswith('.zip'):
            ending = '.zip'
        elif app["download_url"].endswith('.git'):
            ending = '.git'
        else:
            raise InstallError('Only GIT repos, gzip, bzip, and zip packages supported for now')

        # Run webapp preconfig, if any
        try:
            webapp.pre_install(name, vars)
        except Exception, e:
            raise Exception('Error during website config - '+str(e))

        if dbinfo:
            pwd = random_string[0:16]
            dbinfo['name'] = dbinfo['name'] or name
            dbinfo['user'] = dbinfo['user'] or name
            dbinfo['passwd'] = dbinfo['passwd'] or pwd
            try:
                dbase = self.Databases.engines.get(dbinfo['engine'])
                dbase.add(dbinfo['name'])
                dbase.usermod(dbinfo['user'], 'add', dbinfo['passwd'])
                dbase.chperm(dbinfo['name'], dbinfo['user'], 'grant')
            except Exception, e:
                raise InstallError('Databases could not be created - %s' % str(e))

        # Make sure the target directory exists, but is empty
        # Testing for sites with the same name should have happened by now
        target_path = os.path.join(site_dir, name)
        pkg_path = '/tmp/'+name+ending
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        os.makedirs(target_path)

        # Download and extract the source package
        if app["download_url"] and ending == '.git':
            git.Repo.clone_from(app["download_url"], target_path)
        elif app["download_url"]:
            try:
                cat.statusmsg('Downloading webapp package...')
                download(app["download_url"], file=pkg_path, crit=True)
            except Exception, e:
                raise InstallError('Couldn\'t download - %s' % str(e))

            if ending in ['.tar.gz', '.tgz', '.tar.bz2']:
                extract_cmd = 'tar '
                extract_cmd += 'xzf' if ending in ['.tar.gz', '.tgz'] else 'xjf'
                extract_cmd += ' /tmp/%s -C %s --strip 1' % (name+ending, target_path)
            else:
                extract_cmd = 'unzip -d %s /tmp/%s' % (target_path, name+ending)

            status = shell(extract_cmd)
            if status["code"] >= 1:
                raise InstallError(status["stderr"])
            os.remove(pkg_path)

        php = vars["php"] or False
        addtoblock = vars["addtoblock"] or ""

        if addtoblock:
            addtoblock = nginx.loads(addtoblock, False)
        else:
            addtoblock = []
        if app["website_plugin"] == 'Website' and php and addtoblock:
            addtoblock.extend(x for x in webapp.phpblock)
        elif app["website_plugin"] == 'Website' and php:
            addtoblock = webapp.phpblock

        # Setup the webapp and create an nginx serverblock
        try:
            w = {"name": name, "type": app["website_plugin"],
            "path": target_path, "addr": vars["addr"] or "localhost",
            "port": vars["port"] or 80, "php": app["php"] or php or False,
            "version": app["version"].rsplit("-", 1)[0] if app["website_updates"] else None,
            "dbengine": dbinfo["engine"] if dbinfo else None,
            "dbname": dbinfo["name"] if dbinfo else None,
            "dbuser": dbinfo["user"] if dbinfo else None}
            self.component.nginx_add(site=w, 
                add=addtoblock if addtoblock else webapp.addtoblock, 
                )
        except Exception, e:
            raise Exception('nginx serverblock couldn\'t be written - '+str(e))

        try:
            specialmsg = webapp.post_install(name, target_path, vars, dbinfo)
        except Exception, e:
            shutil.rmtree(target_path, True)
            self.component.nginx_remove(w, False)
            raise Exception('Error during website config - '+str(e))

        if enable:
            try:
                self.component.nginx_enable(w)
            except:
                raise ReloadError('nginx')
        if enable and app["php"]:
            try:
                self.component.php_reload()
            except:
                raise ReloadError('PHP-FPM')

        # Add the new path to tracked points of interest (POIs)
        if self.app.storage:
            self.app.storage.append("websites", w)
        self.filesystems.add_point_of_interest(name=name, ptype="website", 
            path=target_path, by="websites", icon=app["icon"], 
            remove=False)

        if specialmsg:
            return specialmsg
    
    def update(self, app, site):
        webapp = self.site_engines.get(app["pid"])

        if not app["download_url"]:
            ending = ''
        elif app["download_url"].endswith('.tar.gz'):
            ending = '.tar.gz'
        elif app["download_url"].endswith('.tgz'):
            ending = '.tgz'
        elif app["download_url"].endswith('.tar.bz2'):
            ending = '.tar.bz2'
        elif app["download_url"].endswith('.zip'):
            ending = '.zip'
        elif app["download_url"].endswith('.git'):
            ending = '.git'
        else:
            raise InstallError('Only GIT repos, gzip, bzip, and zip packages supported for now')

        oldsite = site

        if app["download_url"] and ending == '.git':
            pkg_path = app["download_url"] 
        elif app["download_url"]:
            pkg_path = os.path.join('/tmp', site.name+ending)
            try:
                download(app["download_url"], file=pkg_path, crit=True)
            except Exception, e:
                raise Exception('Couldn\'t update - %s' % str(e))
        try:
            webapp.update(site["path"], pkg_path, site["version"])
        except Exception, e:
            raise Exception('Couldn\'t update - %s' % str(e))
        finally:
            site["version"] = app["version"].rsplit('-', 1)[0]
            c = ConfigParser.RawConfigParser()
            c.read(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'))
            c.set('website', 'version', site.version)
            with open(os.path.join('/etc/nginx/sites-available', '.'+site["name"]+'.ginf'), 'w') as f:
                c.write(f)
        if pkg_path:
            os.unlink(pkg_path)
        if self.app.storage:
            self.app.storage.remove("websites", oldsite)
            self.app.storage.append("websites", site)
    
    def remove(self, app, site):
        webapp = self.site_engines.get(app["pid"])

        if webapp and site["type"] != 'ReverseProxy':
            webapp.pre_remove(site)
        if site["type"] != 'ReverseProxy':
            if site["path"].endswith('_site'):
                shutil.rmtree(site["path"].split('/_site')[0])
            elif site["path"].endswith('htdocs'):
                shutil.rmtree(site["path"].split('/htdocs')[0])
            elif os.path.islink(site["path"]):
                os.unlink(site["path"])
            else:
                shutil.rmtree(site.["path"])
            if site.has_key("dbengine") and site["dbengine"]:
                dbase = self.Databases.engines.get(site['dbengine'])
                dbase.remove(site["dbname"])
                dbase.usermod(site["dbuser"], 'del', '')
        self.component.nginx_remove(site)
        if webapp and site["type"] != 'ReverseProxy':
            webapp.post_remove(site)
            self.filesystems.remove_point_of_interest(path=site["path"])
        if self.app.storage:
            self.app.storage.remove("websites", site)
