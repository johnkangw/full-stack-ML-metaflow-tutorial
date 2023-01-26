

from metaflow import FlowSpec, step, Parameter, JSONType, IncludeFile, card, S3, environment
import os
import json
from dotenv import load_dotenv
load_dotenv('my.env')



class Deployment_Flow(FlowSpec):
    """
    train a random forest
    """
    @card 
    @step
    def start(self):
        """
        Load the data
        """
        #Import scikit-learn dataset library
        from sklearn import datasets
        from sklearn.model_selection import train_test_split

        #Load dataset
        self.iris = datasets.load_iris()
        self.X = self.iris['data']
        self.y = self.iris['target']
        self.labels = self.iris['target_names']

        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(self.X, self.y, test_size=0.2)
        self.next(self.rf_model)
        
    @step
    def rf_model(self):
        """
        build random forest model
        """
        from sklearn.ensemble import RandomForestClassifier
        
        
        self.clf = RandomForestClassifier(n_estimators=10, max_depth=None,
            min_samples_split=2, random_state=0)
        self.next(self.train)

        
        
    @step
    def train(self):
        """
        Train the model
        """
        from sklearn.model_selection import cross_val_score
        self.clf.fit(self.X_train, self.y_train)
        self.y_pred = self.clf.predict(self.X_test)
        self.y_probs = self.clf.predict_proba(self.X_test)
        self.next(self.deploy)

    @step
    def deploy(self):
        """
        Use SageMaker to deploy the model as a stand-alone, PaaS endpoint.
        """
        import os
        import time
        import joblib
        import shutil
        import tarfile
        from sagemaker.sklearn import SKLearnModel

        ROLE = os.getenv('ROLE')
        CODE_LOCATION = os.getenv('CODE_LOCATION')


        model_name = "model"
        local_tar_name = "model.tar.gz"


        os.makedirs(model_name, exist_ok=True)
        # save model to local folder
        joblib.dump(self.clf, f"{model_name}/{model_name}.joblib")
        # save model as tar.gz
        with tarfile.open(local_tar_name, mode="w:gz") as _tar:
            _tar.add(model_name, recursive=True)
        # save model onto S3
        with S3(run=self) as s3:
            with open(local_tar_name, "rb") as in_file:
                data = in_file.read()
                self.model_s3_path = s3.put(local_tar_name, data)
                #print('Model saved at {}'.format(self.model_s3_path))
        # remove local model folder and tar
        shutil.rmtree(model_name)
        os.remove(local_tar_name)
        # initialize SageMaker SKLearn Model
        sklearn_model = SKLearnModel(model_data=self.model_s3_path,
                                     role=ROLE,
                                     entry_point=CODE_LOCATION,
                                     framework_version='0.23-1',
                                     code_location='s3://oleg2-s3-mztdpcvj/sagemaker/')
        endpoint_name = f'HBA-RF-endpoint-{int(round(time.time() * 1000))}'
        print(f"\n\n================\nEndpoint name is: {endpoint_name}\n\n")
        # deploy model
        predictor = sklearn_model.deploy(instance_type='ml.c5.2xlarge',
                                         initial_instance_count=1,
                                         endpoint_name=endpoint_name)
        # prepare a test input and check response
        test_input = self.X
        result = predictor.predict(test_input)
        print(result)

        self.next(self.end)
    
    @step
    def end(self):
        """
        End of flow!
        """
        print("Deployment_Flow is all done.")


if __name__ == "__main__":
    Deployment_Flow()


