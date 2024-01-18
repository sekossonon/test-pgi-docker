import subprocess
import sys
import re
import os

try:
    import pkg_resources
except ImportError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", '--upgrade','pip', 'setuptools', 'wheel'])
    try:
        import pkg_resources
    except ImportError:
        uninstall = subprocess.Popen(
            [sys.executable, "-m", "pip", "uninstall", "setuptools", "--no-input", "-y"])
        install = subprocess.check_call(
            [sys.executable, "-m", "pip", "install", '--upgrade', 'pip', 'setuptools', 'wheel'])
        import pkg_resources
try:
    if "win" in sys.platform and not "darwin" in sys.platform:
        output = subprocess.Popen(
            ['powershell.exe', '-command ', '"& {{ {}\.ressources\export_env.ps1; DisablePythonFileValidation }}"'.format(os.path.dirname(__file__))], stdout=sys.stdout)
        (out, err) = output.communicate()

    pre_commit_pkg = "pre-commit"
    ###############################################################
    ### these lines have been left there for debugging purposes ###
    ###############################################################
    # uninstall = subprocess.Popen([sys.executable, "-m", "pip", "uninstall", pre_commit_pkg, "--no-input", "-y"])
    # uninstall.wait()

    installed_packages = pkg_resources.working_set
    installed_packages_list = [i.key for i in installed_packages]

    if pre_commit_pkg not in installed_packages_list:
        print("{} package not found, proceeding installation process".format(pre_commit_pkg))
        output = subprocess.Popen([sys.executable, "-m", "pip", "install",
                                  pre_commit_pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = output.communicate()
        err = err.decode('utf-8') if err else ""
        out = out.decode('utf-8') if out else ""

        if "Consider adding this directory to PATH" in err:
            # extracts path in string in case install directory has not been added to PATH variable
            # in order to call pre commit everywhere on Linux and (hopefully) Mac systems
            local_repo_toadd = re.search(
                r'((((?<!\w)[A-Z,a-z]:)|(\.{1,2}\\))([^\b%\/\|:\n\"]*))|("\2([^%\/\|:\n\"]*)")|((?<!\w)(\.{1,2})?(?<!\/)(\/((\\\b)|[^ \b%\|:\n\"\\\/])+)+\/?)', err)
            local_repo_toadd = local_repo_toadd.group(0).strip("'")
            if "win" in sys.platform:
                output = subprocess.Popen(
                    ['powershell.exe -ExecutionPolicy RemoteSigned -file "{}\.ressources\export_env.ps1"'.format(os.path.dirname(__file__))], stdout=sys.stdout)

            else:
                perm = os.stat("{}/.ressources/export_env.sh".format(os.path.dirname(__file__)))
                os.chmod("{}/.ressources/export_env.sh".format(os.path.dirname(__file__)), perm.st_mode | 0o111)
                output = subprocess.check_call('./export_env.sh "{}"'.format(local_repo_toadd),
                                               shell=True, cwd="{}/.ressources/".format(os.path.dirname(__file__)))

        print("{} installed".format(pre_commit_pkg))

    else:
        print("{} package found, skipping to next step".format(pre_commit_pkg))

    if "win" in sys.platform:
        subprocess.run(["pre-commit", "install"], cwd="{}".format(os.path.dirname(__file__)), shell=True, start_new_session=True)
    else:
        output = subprocess.run(["pre-commit", "install"], executable="/bin/bash",
                                cwd="{}".format(os.path.dirname(__file__)), shell=True, start_new_session=True)
    print("Pre commit has been initialized for the current directory")
except:
  print("An exception has occured during pre-commit install")
  print("Please capture error output and failure conditions if you can and send it to the tiger team")
