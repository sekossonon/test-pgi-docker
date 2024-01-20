pipeline {
    agent {
        docker { 
            image 'python:3.10-bookworm'
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
        //         python -m venv venv
        //         . venv/bin/activate
        //         pip install --upgrade pip
        //         pip install pre-commit
        //         git config --unset-all core.hooksPath
        //         pre-commit install
        //         pre-commit run --files mic/**/* --show-diff-on-failure
        //         # pre-commit run --from-ref origin/HEAD --to-ref HEAD
        //         '''
        //     }
        // }
        stage('Initializing'){
            steps{
                echo 'install docker'
                sh '''
                apt-get update
                apt-get install ca-certificates curl gnupg
                install -m 0755 -d /etc/apt/keyrings
                curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                chmod a+r /etc/apt/keyrings/docker.gpg
                echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
                $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
                tee /etc/apt/sources.list.d/docker.list > /dev/null
                apt-get update
                apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
                apt-get clean
                '''
                sh 'service docker start'
            }
            
        }
        stage('Cloning dependencies') {
            steps {
                echo 'clone odoo-common 16'
                dir('odoo-common') {
                    echo 'clone oca/projects 16'
                    git branch: '16.0', credentialsId: 'jenkins-upa-test', url: 'https://github.com/microcom/odoo-common.git'
                }
                sh 'mv ./odoo-common ./src/projects/'
                dir('project') {
                    echo 'clone oca/project'
                    git branch: '16.0', url: 'https://github.com/OCA/project.git'
                }
                sh 'mv ./project ./src/projects/'
                sh 'ls -l .'
            }
        }

        stage('Uni Tests') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'my-docker-reg-upa', usernameVariable: 'docker-uname', passwordVariable: 'docker-pwd')]) {
                    echo 'build image'
                    sh '''
                    docker login -u $docker-uname -p $docker-pwd
                    docker build -t my-pgi-16.0:${env.BUILD_ID} .
                    '''
                    echo 'run tests'
                }
            }

        }

    }
}