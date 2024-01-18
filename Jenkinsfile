pipeline {
    agent {
        docker { 
            image 'python:bullseye'
            args '-u root --privileged'
        }
    }

    stages {
        // stage('Code QA') {
        //     steps {
        //         echo 'creating virtual env and install pre-commit'
        //         sh '''
        //         echo $(pwd)
        //         git config --global --add safe.directory $(pwd)
        //         git init .
        //         git status
        //         ls -l .
        //         python -m venv venv
        //         . venv/bin/activate
        //         pip install --upgrade pip
        //         pip install pre-commit
        //         git config --unset-all core.hooksPath
        //         pre-commit install
        //         pre-commit run --files mic/**/* --show-diff-on-failure
        //         pre-commit run --from-ref origin/HEAD --to-ref HEAD
        //         '''
        //     }
        // }
        stage('Testing') {
            steps {
                echo 'clone odoo-common 16'
                sh '''
                git clone --depth=1 --branch=16.0 https://github.com/microcom/odoo-common.git
                '''
                echo 'clone oca/projects 16'
                sh '''
                git clone --depth=1 --branch=16.0 https://github.com/OCA/project.git
                '''
            }
        }
    }
}