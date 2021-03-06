"""
Put a project onto a galaxy server.

After exporting to the galaxy root,
some steps still currently must be done manually.
One step is to copy some of the lines from
the generate file tool_conf.xml.local
to the file tool_conf.xml which is used by the galaxy server.
Another thing is that the file integrated_tool_panel.xml
should be deleted because it saves old elements of the user interface
which should be recomputed for the new exported project.
One tip for running the server is to use --daemon and --stop-daemon
as options to run.sh because the server cannot be killed by ctrl-c
at least in the current galaxy version.
Another tip is to change the host in universe_wsgi.ini to 0.0.0.0
so that it serves on all public interfaces
instead of only the default loopback interface 127.0.0.1
which can only be seen from the server itself.
"""

import re
import os
import sys
import shutil
import subprocess

import argparse
from lxml import etree

import meta
import Util
import galaxyutil


def make_command(module_name, form_objects):
    """
    The python call is implicit.
    @param module_name: something like '20100707a'
    @param form_objects: a list of input parameter objects
    @return: a single line string with placeholders
    """
    elements = [
            'auto.py', module_name,
            '--output_filename_for_galaxy=$out_file1']
    for obj in form_objects:
        if not obj.web_only():
            elements.append(obj.get_galaxy_cmd())
    return ' '.join(elements)

def get_xml(usermod, module_name, short_name):
    """
    Get the galaxy XML describing a single tool.
    @param usermod: module object
    @param module_name: something like '20100707a'
    @param short_name: something like 'plot_pca_3d'
    @return: contents of a galaxy XML interface file
    """
    # get module info
    form_objects = usermod.get_form()
    if hasattr(usermod, 'get_form_out'):
        form_out = usermod.get_form_out()
    else:
        raise FormOutError(
                'snippet %s provides no output '
                'format information' % module_name)
    doc_lines = Util.get_stripped_lines(usermod.__doc__.splitlines())
    try:
        tags = usermod.g_tags
    except AttributeError:
        tags = []
    # create the python command string with wildcards
    cmd = make_command(module_name, form_objects)
    # build the xml
    desc_prefix, desc_suffix = galaxyutil.get_split_title(doc_lines[0])
    tool = etree.Element('tool',
            id=short_name, name=desc_prefix, version='1.0.0')
    if desc_suffix:
        etree.SubElement(tool, 'description').text = desc_suffix
    etree.SubElement(tool, 'command', interpreter='python').text = cmd
    inputs = etree.SubElement(tool, 'inputs')
    outputs = etree.SubElement(tool, 'outputs')
    # add inputs
    for obj in form_objects:
        if not obj.web_only():
            obj.add_galaxy_xml(inputs)
    # add output
    etree.SubElement(outputs, 'data',
            format=form_out.get_galaxy_format(),
            name='out_file1')
    # Add the format tweak if there is an image.
    # This is a hack required because galaxy does not
    # play well with apps which have varying output formats.
    # See the EMBOSS apps for more examples.
    if 'imageformat' in [x.label for x in form_objects]:
        etree.SubElement(tool, 'code', file='galaxy_format_tweak.py')
    # serialize the xml
    return etree.tostring(etree.ElementTree(tool), pretty_print=True)

def add_xml_files(galaxy_root, module_names, short_name_length, tools_subdir):
    """
    The XML files are added under two conditions.
    Under the first condition the files are added directly to galaxy.
    In this case only the XML filenames are subsequently needed to
    create the toolbox XML file.
    Under the second condition the files are added to a tool suite archive.
    In this case the id, name, and description of the added modules
    are needed to create the suite configuration XML file.
    This function is concerned with the first case.
    @param galaxy_root: root of the galaxy installation
    @param module_names: generally uninformative names of modules
    @param short_name_length: max length of unique short module names
    @param tools_subdir: subdirectory of galaxy_root
    @return: a list of xml filenames, and a list of import errors
    """
    mod_infos, import_errors = meta.get_usermod_info(
            module_names, short_name_length)
    # Get the xmls.
    xml_filenames = []
    nsuccesses = 0
    nfailures = 0
    for info in mod_infos:
        usermod = info.get_usermod()
        name = info.get_name()
        short_name = info.get_identifier()
        xml_content = None
        try:
            xml_content = get_xml(usermod, name, short_name)
            nsuccesses += 1
        except Exception as e:
            print >> sys.stderr, '%s: error making xml: %s' % (name, str(e))
            nfailures += 1
        if xml_content:
            xml_filename = short_name + '.xml'
            xml_pathname = os.path.join(
                    galaxy_root, 'tools', tools_subdir, xml_filename)
            with open(xml_pathname, 'w') as fout:
                fout.write(xml_content)
            xml_filenames.append(xml_filename)
    print >> sys.stderr, len(import_errors), 'import errors'
    print >> sys.stderr, nfailures, 'failures to create an xml'
    print >> sys.stderr, nsuccesses, 'successfully created xmls'
    return xml_filenames, import_errors

def add_xml_archive_files(module_names, short_name_length, archive):
    """
    The XML files are added under two conditions.
    Under the first condition the files are added directly to galaxy.
    In this case only the XML filenames are subsequently needed to
    create the toolbox XML file.
    Under the second condition the files are added to a tool suite archive.
    In this case the id, name, and description of the added modules
    are needed to create the suite configuration XML file.
    This function is concerned with the second case.
    @param module_names: generally uninformative names of modules
    @param short_name_length: max length of unique short module names
    @param archive: the path to the output directory to be tarred
    @return: a list of added module infos, and a list of import errors
    """
    mod_infos, import_errors = meta.get_usermod_info(
            module_names, short_name_length)
    # Get the xmls.
    added_infos = []
    nsuccesses = 0
    nfailures = 0
    for info in mod_infos:
        usermod = info.get_usermod()
        name = info.get_name()
        short_name = info.get_identifier()
        xml_content = None
        try:
            xml_content = get_xml(usermod, name, short_name)
            nsuccesses += 1
        except Exception as e:
            print >> sys.stderr, '%s: error making xml: %s' % (name, str(e))
            nfailures += 1
        if xml_content:
            xml_pathname = os.path.join(archive, short_name + '.xml')
            with open(xml_pathname, 'w') as fout:
                fout.write(xml_content)
            added_infos.append(info)
    print >> sys.stderr, len(import_errors), 'import errors'
    print >> sys.stderr, nfailures, 'failures to create an xml'
    print >> sys.stderr, nsuccesses, 'successfully created xmls'
    return added_infos, import_errors

def get_toolbox_xml(section_name, section_id, tools_subdir, xml_filenames):
    """
    @param section_name: the section name
    @param section_id: the section id
    @param tools_subdir: the name of the tools subdirectory, not a full path
    @param xml_filenames: xml filenames, not full paths
    @return: contents of a toolbox xml file
    """
    # build the xml
    toolbox = etree.Element('toolbox')
    section = etree.SubElement(toolbox, 'section',
            name=section_name, id=section_id)
    # add the items
    for filename in xml_filenames:
        target = os.path.join(tools_subdir, filename)
        etree.SubElement(section, 'tool', file=target)
    # serialize the xml
    return etree.tostring(etree.ElementTree(toolbox), pretty_print=True)

def get_suite_config_xml(added_infos, suite_name):
    """
    Create suite_config.xml contents for a galaxy tool suite archive.
    @param added_infos: ImportedModuleInfo objects for added tools
    @param suite_name: the name of the suite directory, not the whole path
    @return: contents of suite_config.xml
    """
    suite = etree.Element('suite', id=suite_name,
            name='Suite of misc tools', version='1.0.0')
    suite_description = 'Suite of misc tools for Galaxy'
    etree.SubElement(suite, 'description').text = suite_description
    for info in added_infos:
        module_id = info.get_identifier()
        module_name = galaxyutil.get_split_title(info.get_title())[0]
        module_description = info.get_title()
        tool = etree.SubElement(suite, 'tool',
                id=module_id, name=module_name, version='1.0.0')
        etree.SubElement(tool, 'description').text = module_description
    return etree.tostring(etree.ElementTree(suite), pretty_print=True)

def main_non_archive(args):
    # validation
    if not args.galaxy_root:
        raise ValueError(
                'in non-archive mode the galaxy root must be specified')
    if not args.tools_subdir:
        raise ValueError(
                'in non-archive mode the tools subdirectory must be specified')
    # get the module names
    module_names = meta.get_module_names(
            args.manifest, args.create_all, args.create_tagged)
    # create the python subtree
    tools_subdir_path = os.path.join(
            args.galaxy_root, 'tools', args.tools_subdir)
    meta.add_python_files(module_names, tools_subdir_path)
    shutil.copyfile('galaxy_format_tweak.py',
            os.path.join(tools_subdir_path, 'galaxy_format_tweak.py'))
    # create the galaxy xml interface files
    xml_filenames, import_errors = add_xml_files(args.galaxy_root,
            module_names, args.short_length, args.tools_subdir)
    for e in import_errors:
        print e
    # create the toolbox xml pointing to the installed xmls
    toolbox_pathname = os.path.join(args.galaxy_root, args.tool_conf)
    section_name = args.tools_subdir
    section_id = args.tools_subdir
    toolbox_xml = get_toolbox_xml(section_name, section_id,
            args.tools_subdir, xml_filenames)
    with open(toolbox_pathname, 'wt') as fout:
        fout.write(toolbox_xml)

def main_archive(args):
    # validation
    if args.galaxy_root:
        raise ValueError(
                'in archive mode the galaxy root must not be specified')
    if args.tools_subdir:
        raise ValueError(
                'in archive mode the tools subdirectory must not be specified')
    # define the archive extension and the compression command
    archive_extension = '.tar.bz2'
    archive_prefix = os.path.basename(args.suite_archive.rstrip('/'))
    archive_name = archive_prefix + archive_extension
    archive_cmd = ['tar', 'cjvf', archive_name, args.suite_archive]
    # delete the suite directory and archive if they exist
    try:
        shutil.rmtree(args.suite_archive)
        os.remove(archive_name)
    except OSError as e:
        pass
    # get the module names
    module_names = meta.get_module_names(
            args.manifest, args.create_all, args.create_tagged)
    # create the empty suite directory
    os.makedirs(args.suite_archive)
    # add the python files
    meta.add_python_files(module_names, args.suite_archive)
    shutil.copyfile('galaxy_format_tweak.py',
            os.path.join(args.suite_archive, 'galaxy_format_tweak.py'))
    # create the galaxy xml interface files
    mod_infos, import_errors = add_xml_archive_files(
            module_names, args.short_length, args.suite_archive)
    for e in import_errors:
        print e
    # create the toolbox xml pointing to the installed xmls
    config_pathname = os.path.join(args.suite_archive, 'suite_config.xml')
    config_xml = get_suite_config_xml(mod_infos, archive_prefix)
    with open(config_pathname, 'wt') as fout:
        fout.write(config_xml)
    # use subprocess instead of tarfile to create the tgz
    subprocess.call(archive_cmd)

def main(args):
    if args.suite_archive:
        main_archive(args)
    else:
        main_non_archive(args)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',
            help='create xmls for snippets listed in this file')
    parser.add_argument('--create_all', action='store_true',
            help='create xmls for all snippets')
    parser.add_argument('--create_tagged',
            help='create xmls for snippets with this tag')
    parser.add_argument('--short_length', type=int, default=20,
            help='max length of shortened snippet names')
    parser.add_argument('--suite_archive',
            help='create this directory and a corresponding archive')
    parser.add_argument('--galaxy_root',
            help='path to the Galaxy root directory')
    parser.add_argument('--tool_conf', default='tool_conf.xml.local',
            help='a toolbox xml will be created with this filename')
    parser.add_argument('--tools_subdir',
            help='python files, const data are copied to this galaxy subdir')
    main(parser.parse_args())
