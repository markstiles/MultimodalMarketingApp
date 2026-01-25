
import { experimental_createXMCClient } from '@sitecore-marketplace-sdk/xmc';

// Need to await it because it might return a promise or the client itself is async created?
// The code says: const xmc = await experimental_createXMCClient(...)

(async () => {
    const client = await experimental_createXMCClient({
      getAccessToken: async () => 'dummy-token'
    });

    console.log('Client keys:', Object.keys(client));

    function inspect(obj, name) {
        if(!obj) {
            console.log(`${name} is undefined`);
            return;
        }
        console.log(`\n--- ${name} ---`);
        
        let props = [];
        let p = obj;
        while(p && p !== Object.prototype) {
             props = props.concat(Object.getOwnPropertyNames(p));
             p = Object.getPrototypeOf(p);
        }
        // unique and sort
        props = [...new Set(props)].sort();
        console.log(props);
    }

    inspect(client.agent, 'client.agent');
    inspect(client.pages, 'client.pages');
    inspect(client.sites, 'client.sites');
    inspect(client.authoring, 'client.authoring');
})();



