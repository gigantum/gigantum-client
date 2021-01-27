export default {
  finished: (callbackData) => {
    const { response, successCall, mutations } = callbackData;
    const metaDataArr = JSON.parse(response.data.jobStatus.jobMetadata).dataset.split('|');
    const owner = metaDataArr[1];
    const datasetName = metaDataArr[2];
    mutations.FetchDatasetEdgeMutation(
      owner,
      datasetName,
      (error) => {
        if (error) {
          console.error(error);
        }
        successCall(owner, datasetName);
      },
    );
  },
  failed: (callbackData) => {
    const { response, failureCall } = callbackData;
    let errorMessage = response.data.jobStatus.failureMessage;
    const failureDetail = JSON.parse(response.data.jobStatus.jobMetadata).failure_detail;
    errorMessage = errorMessage.indexOf(':') ? errorMessage.split(':')[1] : errorMessage;

    failureCall(response.data.jobStatus.failureMessage, failureDetail);
    return {
      errorMessage,
      reportedFailureMessage: failureDetail,
    };
  },
};
