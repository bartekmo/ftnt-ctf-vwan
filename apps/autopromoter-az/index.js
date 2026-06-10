const axios = require('axios');
const https = require('https');
const config = require('./config.json');

const unsafeAgent = new https.Agent({
    rejectUnauthorized: false,
})
const api = axios.create({
    httpsAgent: unsafeAgent,
    baseURL: `https://${process.env.FMG_ADDRESS}/jsonrpc`,
    timeout: 30000
})

let sessionId = '';
let cmdId = 1;

function execLogin() {
    // start a fresh FMG API session
    let postBody = {
        "id": cmdId++,
        "method": "exec",
        "params": [
            {
                "data": {
                    "user": config.fmg_user,
                    "passwd": config.fmg_passwd
                },
                "url": "/sys/login/user"
            }
        ]
    }
    return api.post('', postBody);
}

function getDevList() {
    // gets list of unregistered devices in root ADOM
    let postBody = {
        "id": cmdId++,
        "method": "get",
        "session": sessionId,
        "params": [
            {
                "url": "/dvmdb/adom/root/device",
                "loadsub": 0,
                "filter": [
                    ["mgmt_mode", "==", 0]
                ]
            }
        ]
    }
    return api.post('', postBody);
}

function promoteDev(devName, adomName) {
    let postBody = {
        "id": cmdId++,
        "method": "exec",
        "session": sessionId,
        "params": [{
            "url": "/dvm/cmd/add/device",
            "data": {
                "adom": adomName,
                "device": {
                    "adm_pass": "",
                    "adm_user": "admin",
                    "device action": "promote_unreg",
                    "name": devName
                },
                "flags": [
                    "create_task"
                ]
            }
        }]
    }
    return api.post('', postBody);
}

function execLogout() {
    let postBody = {
        "method": "exec",
        "params": [{
            "url": "/sys/logout"
        }],
        "session": sessionId,
        "id": cmdId++
    }
    return api.post('', postBody);
} //execLogout()


/********************************* main **********************************/

execLogin()
    .then(res => {
        if ( res.data.result[0].status.code != 0 ) {
            throw new Error(res.data.result[0].status.message);
            return -1;
        }
        //console.log(res.data.result[0].status)
        sessionId = res.data.session;
    })
    .then( async () => {
        let devList = await getDevList();
        const promises = [];
        devList.data.result[0].data.forEach(dev => {
            let tmp = dev.name.split('-')[0];
            let indxPad = tmp.substring(tmp.length-2)
            console.log(`${dev.name} ==> hub${indxPad}`);
            const promise = promoteDev(dev.name, `${config.adomPrefix}${indxPad}`)
                /*.then(resPromote => {
                    if (resPromote.data.result[0].status.code<0) {
                        console.error(`Error promoting ${dev.name}. ${resPromote.data.result[0].status.message} (${resPromote.data.result[0].status.code})`)
                    }
                })
                .catch(err=>{
                    console.error(`Error promoting ${dev.name}. ${err}`)
                });*/
            promises.push(promise);
        })
        return Promise.all(promises);
    })
    .then(()=>{
        execLogout();
    })
    .catch(err => {
        console.error(`Error logging into FMG at ${err.request._currentRequest.host}: ${err.message}`)
    })