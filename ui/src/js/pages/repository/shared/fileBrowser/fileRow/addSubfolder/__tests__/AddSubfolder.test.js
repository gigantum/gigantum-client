// import initStoryshots, { Stories2SnapsConverter } from '@storybook/addon-storyshots';
// import { mount } from 'enzyme';
// import toJson from 'enzyme-to-json';
// import path from 'path';

// const converter = new Stories2SnapsConverter();

// console.log('this ran');

// initStoryshots({
//   framework: 'react',
//   configPath: path.join(__dirname, './AddSubfolder.stories.jsx'),
//   test: ({ story, context }) => {
//     const snapshotFileName = converter.getSnapshotFileName(context);
//     const storyElement = story.render();
//     const shallowTree = mount(storyElement);


//     if (snapshotFileName) {
//       expect(toJson(shallowTree)).toMatchSpecificSnapshot(snapshotFileName);
//     }
//   },
// });

// export default {};
