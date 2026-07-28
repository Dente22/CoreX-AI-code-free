'use strict';

/** Папки библиотеки CoreX, обязательные в extraResources установщика. */
function getRequiredLibraryResources() {
  return [
    { from: '../core_x_agents', to: 'core_x_agents' },
    { from: '../core_x_skills', to: 'core_x_skills' },
    { from: '../core_x_knowledge', to: 'core_x_knowledge' },
  ];
}

module.exports = { getRequiredLibraryResources };
