#!/usr/bin/env python
# -*- coding: utf-8 -*-

from git import Repo
from jira import JIRA

import ConfigParser
import sys

CONFIG_FILE = 'deployment.ini'
VERBOSE = True

repo = Repo()
git = repo.git
args = sys.argv


class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''


def print_out(message, message_type=Color.OKGREEN):
    if VERBOSE:
        print(message_type + message + Color.ENDC)


def get_config():
    config = ConfigParser.ConfigParser()
    config.read(CONFIG_FILE)
    return config


def update_config(config):
    with open(CONFIG_FILE, 'wb') as configfile:
        config.write(configfile)


def get_jira_issues():
    config = get_config()
    search_pattern = config.get('JIRA', 'search_pattern')
    search_key = search_pattern.format(
        config.get('JIRA', 'project'),
        config.get('JIRA', 'fix_version')
    )
    username = config.get('JIRA', 'username')
    password = config.get('JIRA', 'password')

    options = {'server': config.get('JIRA', 'server')}

    try:
        jira = JIRA(options, basic_auth=(username, password))
    except:
        print_out('Invalid JIRA credentials', Color.FAIL)
        sys.exit()

    return jira.search_issues(search_key)


def delete_branch(branch, is_remote=False):
    if is_remote:
        try:
            git.push('origin', ':{}'.format(branch))
            print_out('Deleted remote {} branch.'.format(branch))
        except:
            print_out(
                'Remote {} cannot be deleted'.format(branch), Color.WARNING
            )
    else:
        try:
            git.branch('-D', branch)
            print_out('Deleted local {} branch.'.format(branch))
        except:
            print_out(
                'Local {} cannot be deleted'.format(branch), Color.WARNING
            )


def prepare_staging():
    git.checkout('master')

    delete_local_branches()

    git.fetch('--all')
    git.pull('origin', 'master')
    print_out('Updated Master')

    delete_branch('staging')
    delete_branch('staging', is_remote=True)

    git.checkout('HEAD', b='staging')
    print_out('Checkout staging')
    for issue in get_jira_issues():
        git.merge('origin/{}'.format(issue.key))
        print_out('%s merged' % issue.key)

    git.push('origin', 'staging')
    print_out('Pushed staging')


def create_version(version, rc_version):
    config = get_config()
    config.set('PROJECT', 'rc_version', rc_version)
    config.set('PROJECT', 'version', version)
    update_config(config)

    index = repo.index
    index.add(['deployment.ini'])
    index.commit(config.get('PROJECT', 'bump_message'))

    git.push('origin', 'staging')
    return version, rc_version


def create_tag(version, rc_version, is_main_version=False):
    tag = '{}rc{}'.format(version, rc_version)
    if is_main_version:
        tag = version

    config = get_config()
    try:
        tag_message = config.get('PROJECT', 'tag_message')
        repo.create_tag(tag, message=tag_message.format(tag))
        print_out('Created tag: {} rc{}'.format(version, rc_version))
    except Exception as error:
        print_out('Tag cannot be created {}'.format(error), Color.FAIL)
        sys.exit()


def push_tag(version, rc_version):
    decision = raw_input('Do you want to push main version: [Y/N] ').upper()
    if decision == 'Y':
        create_tag(version, rc_version, True)
        repo.remotes.origin.push(version)
        print_out('Pushed {}'.format(version))

    tag = '%src%s'.format(version, rc_version)
    repo.remotes.origin.push(tag)
    print_out('Pushed {}'.format(tag))


def delete_local_branches():
    for issue in get_jira_issues():
        delete_branch(issue.key)


def check_tags(version, rc_version):
    rc_version = '{}rc{}'.format(version, rc_version)
    for tag in repo.tags:
        if tag.name in [rc_version, version]:
            print_out('{} already exists'.format(tag.name), Color.FAIL)
            sys.exit()


def get_merged_branches():
    config = get_config()
    project = config.get('JIRA', 'project').upper()
    pattern = '{}-'.format(project)
    diff = git.log('master...staging')
    diff = diff.replace('\n', ' ')
    diff = diff.replace('\r', ' ')
    diff = diff.split(' ')
    diff = set('- ' + w for w in diff if pattern in w and 'origin' not in w)

    print_out('New feature branches', Color.HEADER)
    print_out('\n'.join(diff))


def splash():
    print_out("""
    　　　　　　　　　 　 　 　 .　-‐-　 、
　　　　　　　　　, 　 '"´7:_:ゝ　　　　｀丶､
　　　＿ -‐　 ´￣　 ヽ　　　　　　　 　 　 ｀ｰ'"´￣｀ヽ、
　 ／::r:､｀ﾌ　　　　　　　　　　　　　　　　　　　'ﾞ"ﾞ,ミ　 }
　ヾ):::｀;ｼ′　　　　　　　　　　　　　　　 　 　 　 '^ 　 /
　 {`ｰ'′　　　　　　　　　　　　　　　　　　　　　 　 , '
　　､/＝==--=＝'　　　　　　　　 　 　 　 　 　 j　　ヽ
　　 ﾞ.　　 　 　 　 　 　 ﾆ　　　　　　　　　　　 、　　　 ＼
　　　ヽ､　　　　　　　､｀　　　　　　　　 　 　 ;
　　 　 　 ｀^〈、､､　'^　　　 　 　 　 　 　 　 '′
　　　　　　　 '.　　　　　　　　　　　　　　 ; :
　　　　　　　　,　　　　 　 　 　 　 　 　 ;'′
　　　　　　　　'. : :　　 　 　 　 ,　,
　　　　　 　 　 }　　　 　 　 　 '　′
   """, message_type=Color.HEADER)


if __name__ == '__main__':
    splash()
    version = raw_input('Version: ')
    rc_version = raw_input('RC Version: ')
    check_tags(version, rc_version)

    prepare_staging()
    create_version(version, rc_version)
    create_tag(version, rc_version)
    get_merged_branches()
    if '--delete-local-branches' in args:
        delete_local_branches()

    push_tag(version, rc_version)
