/**
* Project.js
*
* @description :: TODO: You might write a short summary of how this model works and what it represents here.
* @docs        :: http://sailsjs.org/#!documentation/models
*/

module.exports = {

  schema: true,
  
  attributes: {

    // One-to-many association
    user: { 
      model: 'User', 
      required: true 
    },

    // Project name
    name: {
      type: 'string',
      required: true
    },

    // Targets used by this project
    targets: {
      collection: 'Target'
    },

    // Applications used by this project
    applications: {
      collection: 'Application'
    },

    // Analyses used by this project
    analyses: {
      collection: 'Analysis'
    }

  }
};
