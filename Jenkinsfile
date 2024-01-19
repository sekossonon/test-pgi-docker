pipeline {
    agent {
        docker { 
            image 'python:bullseye'
            args '-u root --privileged'
        }
    }
    environment {
        dockerImage = 'pgi'
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
        stage('Cloning dependencies') {
            steps {
                echo 'clone odoo-common 16'
                dir('odoo-common') {
                    git branch: '16.0', credentialsId: 'jenkins-upa-test', url: 'https://github.com/microcom/odoo-common.git'
                    echo 'clone oca/projects 16'
                }
                dir('project') {
                    git branch: '16.0', url: 'https://github.com/OCA/project.git'
                }
                echo 'install docker'
                sh 'apt-get update && apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y'
                sh 'docker image list'
            }
        }

        stage('Test') {
            steps {
                echo 'Test'
                sh "ls -l ."
            }

        }

    }
}