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
    }
}