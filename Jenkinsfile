pipeline {
    agent {
        docker { image 'python:bullseye' }
    }

    stages {
        stage('Test') {
            steps {
                echo 'Testing python version'
                sh python --version
            }
        }
        // stage('Setting up virtual env') {
        //     steps {
        //         echo 'creating virtual env and install pre-commit'
        //         sh '''
        //         cd mic
        //         python3 -m venv venv
        //         source venv/bin/activate
        //         pip install pre-commit
        //         pre-commit install
        //         '''
        //     }
        // }
        // stage('Running pre-commit') {
        //     steps {
        //         echo 'running pre-commit'
        //         sh '''
        //         pre-commit run --all-files
        //         '''
        //     }
        // }
    }
}