"""
This experimental script will run other scripts.
It should import the script as a module and then
use the get_request function in the module to
get the interface.
"""

from StringIO import StringIO
import sys
import textwrap

import argparse

import Form

class ArgHolder(object): pass

class UsageError(Exception): pass

def argv_to_dict(argv):
    d = {}
    for v in argv[2:]:
        if not v.startswith('--'):
            raise UsageError('incorrect subcommand syntax')
        v = v[2:]
        prefix, sep, suffix = v.partition('=')
        if prefix in d:
            raise UsageError('repeated argument ' + prefix)
        if sep:
            d[prefix] = suffix
        else:
            d[prefix] = True
    return d

def dict_to_args(d):
    args = ArgHolder()
    for k, v in d.items():
        setattr(args, k, v)
    return args

def get_output_filename_for_galaxy(argv):
    """
    @param argv: all arguments
    @return: None or the output filename for galaxy
    """
    for arg in argv:
        if arg.startswith('--output_filename_for_galaxy'):
            a, b, c = arg.partition('=')
            return c

def main():
    if len(sys.argv) < 2:
        raise UsageError('not enough params')
    script_name, module_name = sys.argv[:2]
    usermod = __import__(module_name, globals(), locals(), [], -1)
    form_objects = usermod.get_form()
    if '--help' in sys.argv:
        print usermod.__doc__
        print Form.get_help_string(form_objects)
        return
    else:
        d_in = argv_to_dict(sys.argv)
        d_out = {}
        for obj in form_objects:
            if not obj.web_only():
                obj.process_cmdline_dict(d_in, d_out)
        args = dict_to_args(d_out)
        args.contentdisposition = 'attachment'
        if hasattr(usermod, 'get_response_content'):
            content = usermod.get_response_content(args)
        else:
            deprecated_header_pairs, content = usermod.get_response(args)
        output_filename_for_galaxy = get_output_filename_for_galaxy(sys.argv)
        if output_filename_for_galaxy:
            with open(output_filename_for_galaxy, 'w') as fout:
                fout.write(content)
        elif '--write_to_file_for_mobyle' in sys.argv:
            form_out = usermod.get_form_out()
            filename = form_out.get_filename(args)
            with open(filename, 'w') as fout:
                fout.write(content)
        else:
            sys.stdout.write(content)

if __name__ == '__main__':
    usage = textwrap.dedent("""
    example usages of auto.py:
      $ python auto.py 20100623a --help
      $ python auto.py 20100623a --table_a=foo.txt --table_b=bar.txt
    """).strip()
    try:
        main()
    except UsageError as e:
        out = StringIO()
        print >> out, str(e)
        print >> out, ' '.join(sys.argv)
        print >> out, usage
        raise UsageError(out.getvalue())
