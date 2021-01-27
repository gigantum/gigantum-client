import {
  commitMutation,
  graphql,
} from 'react-relay';
import environment from 'JS/createRelayEnvironment';


const mutation = graphql`
  mutation SetBundledAppMutation($input: SetBundledAppInput!){
    setBundledApp(input: $input){
      environment {
        bundledApps {
          id
          owner
          name
          appName
          description
          port
          command
        }
      }
      clientMutationId
    }
  }
`;

let tempID = 0;


export default function SetBundledAppMutation(
  owner,
  labbookName,
  appName,
  description,
  port,
  command,
  callback,
) {
  const variables = {
    input: {
      owner,
      labbookName,
      appName,
      description,
      port,
      command,
      clientMutationId: `${tempID++}`,
    },
  };
  commitMutation(
    environment,
    {
      mutation,
      variables,
      onCompleted: (response, error) => {
        if (error) {
          console.log(error);
        }
        callback(response, error);
      },
      onError: err => console.error(err),
    },
  );
}
