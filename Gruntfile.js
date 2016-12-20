os = require('os');

// Core pieces
if (process.env.DEPLOY_DIRECTORY) {
    var DEPLOY_DIR = process.env.DEPLOY_DIRECTORY + '/';
} else {
    var DEPLOY_DIR = 'deploy_local/';
}    


const CLIENT_DIR = DEPLOY_DIR +'static';
const SERVER_DIR = DEPLOY_DIR +'server';
const LIBRARY_DIR = 'lib';


const JS_SRC=[];

// Building the deployment files
const CLIENT_FILES_SRC_DIR="static";
const CLIENT_FILES=['**/*.html', '**/*.css',  '**/*.json', '**/*.gspec', '**/*.svg', 'Jet.js', '**/*.png', '**/*.jpg', '**/*.zip'];

const SERVER_FILES_SRC_DIR="server";
const SERVER_FILES=['**/*.json', '*.yaml', '**/*.py', '**/*.jinja.*', 'local_mode.flag'];
const ROOT_SERVER_FILES=['app.yaml', 'index.yaml', 'cron.yaml','appengine_config.py'];

const LIB_FILES_SRC_DIR="bower_components";
const LIB_FILES=["*/*.map", "*/*.js", "*/*.css", "*/dist/*"];

// copy and watch take their files in different formats.  This function lets us use one file list for both.
function watchify(prefix, paths) {
    return paths.map(function(path) {
	return prefix + "/" + path
    })
}

module.exports = function(grunt) {
    // Project configuration.
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),

        // Copy bower components.
        copy: {
			client: {
				files: [
					{
						expand: true,
						cwd: CLIENT_FILES_SRC_DIR,
						src: CLIENT_FILES,
						dest: CLIENT_DIR
					}
				]
			},
			server: {
				files: [
					{
						cwd: ".",
						src: ROOT_SERVER_FILES,
						dest: DEPLOY_DIR
					},
					{
						expand: true,
						cwd: SERVER_FILES_SRC_DIR,
						src: SERVER_FILES,
						dest: SERVER_DIR
					}
				]
			},
			libs: {
				files: [
					// Bower components.
					{
						expand: true,
						cwd: LIB_FILES_SRC_DIR,
						src: LIB_FILES,
						dest: [CLIENT_DIR, LIBRARY_DIR].join('/') + '/'
					}
				]
			}
		},


		wait: {
			options: {
			delay: 10000
			}
		},

		typescript: {
			options : {
				target: "es5"
			},
			base: {
				src : JS_SRC,
				dest: "Jet/Jet.js"
			}
		},
		exec : {
			vendorize: {
				command: 'python utils/VendorizorUtil.py' + " --target " + DEPLOY_DIR +"/python_libs"
			},
			vendorize_deploy: {
				command: 'python utils/VendorizorUtil.py' + " --target " + DEPLOY_DIR+"/python_libs" + " --deploy"
			}
		},
		watch : {
			ts : {
				files : JS_SRC,
				tasks : ["typescript"]
			},
			client : {
				files : watchify(CLIENT_FILES_SRC_DIR, CLIENT_FILES),
				tasks : ["copy:client"]
			},
			server : {
				files : watchify(SERVER_FILES_SRC_DIR, SERVER_FILES).concat(ROOT_SERVER_FILES),
				tasks : ["copy:server"]
			},
			libs : {
				files : watchify(LIB_FILES_SRC_DIR, LIB_FILES),
				tasks : ["copy:libs"]
			}

		},
		bower : {
			install : {
			}
		},

		clean : {
			options: {
			force: true
			},
			tidy: [DEPLOY_DIR + "/*"],
			scrub: ["libs/typings", "libs/nodes_modules", "libs/bower_components"]
		},
		tsd : {
			refresh : {
				options :{
					command: "reinstall",
					config:"./tsd.json"
				}
			}
		}

    });

    grunt.loadNpmTasks('grunt-contrib-copy');
    grunt.loadNpmTasks('grunt-contrib-rename');
    grunt.loadNpmTasks('grunt-contrib-connect');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-open');
    grunt.loadNpmTasks('grunt-run');
    grunt.loadNpmTasks('grunt-wait');
    grunt.loadNpmTasks('grunt-typescript');
    grunt.loadNpmTasks('grunt-contrib-clean');
    grunt.loadNpmTasks('grunt-bower-task');
    grunt.loadNpmTasks('grunt-tsd');
    grunt.loadNpmTasks('grunt-exec');


    // Default task(s).
    grunt.registerTask('build_local', ['bower', 'clean:tidy', 'copy:server',  'copy:client', 'copy:libs',  'exec:vendorize']);
    grunt.registerTask('build_deploy', ['bower', 'clean:tidy', 'copy:server', 'copy:client', 'copy:libs', 'exec:vendorize_deploy']);
    grunt.registerTask('default', ['build_local']);
};
